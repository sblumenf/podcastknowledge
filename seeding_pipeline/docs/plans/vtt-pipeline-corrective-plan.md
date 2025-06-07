# VTT Pipeline Corrective Plan

**Purpose**: Fix critical issues preventing VTT pipeline from running  
**Scope**: Minimum changes for basic functionality only  
**Status**: PARTIALLY IMPLEMENTED - Blocked by system restrictions

## Phase 1: Dependency Installation ❌ BLOCKED

### 1.1 Install Core Dependencies ❌
```bash
pip3 install -r requirements-minimal.txt
```

**Critical packages needed**:
- networkx==3.1 (blocking all imports)
- psutil==5.9.6 (required by VTT parser)
- neo4j==5.11.0 (database connectivity)
- google-generativeai==0.3.0 (LLM extraction)

### 1.2 Verify Installation ❌
```bash
python3 -c "import networkx, psutil, neo4j, google.generativeai; print('Dependencies OK')"
```

## Phase 2: Fix Import Issues ✅ COMPLETED

### 2.1 Fix Module Naming Conflict ✅
- Rename `src/utils/logging.py` to `src/utils/log_utils.py`
- Update all imports from `src.utils.logging` to `src.utils.log_utils`

### 2.2 Fix Package Initialization ✅
- Remove circular import in `src/__init__.py`
- Make imports lazy or remove unnecessary ones

## Phase 3: Basic Functionality Test ❌ BLOCKED

### 3.1 Test VTT Parser ❌
```python
from src.vtt.vtt_parser import VTTParser
parser = VTTParser()
segments = parser.parse("test_data/hour_podcast_test.vtt")
print(f"Parsed {len(segments)} segments")
```

### 3.2 Test CLI ❌
```bash
python3 -m src.cli.cli --help
python3 -m src.cli.cli health
```

### 3.3 Test Pipeline (Dry Run) ❌
```bash
python3 -m src.cli.cli process-vtt test_data/hour_podcast_test.vtt --dry-run
```

## Phase 4: Verify Core Components ❌ BLOCKED

### 4.1 Neo4j Connection ❌
- Ensure Neo4j container is running
- Test connection with provided credentials
- Create test node to verify write access

### 4.2 Google API ❌
- Verify GOOGLE_API_KEY is set
- Test minimal LLM call
- Check rate limits

## Success Criteria

**Minimum viable pipeline**:
1. ✅ Can import all modules without errors
2. ✅ CLI help command works
3. ✅ Can parse a VTT file
4. ✅ Can connect to Neo4j
5. ✅ Can make LLM API calls
6. ✅ Can run simple end-to-end test

**NOT Required** (can remain broken):
- Complex features (importance scoring, etc.)
- All tests passing
- Performance optimizations
- Advanced error handling

## Estimated Effort

This corrective plan focuses only on making the pipeline runnable. It should take less than 2 hours to implement these fixes and achieve basic functionality.