# Current CLI Flow Analysis

## Current Broken Execution Path

### CLI Entry Point
```
src/cli/cli.py:process_vtt() [Lines 592-740]
```

### Step-by-Step Execution Flow

1. **Configuration Loading** [Lines 601-606]
   ```python
   config = PipelineConfig.from_file(args.config) or PipelineConfig()
   ```

2. **Pipeline Initialization** [Line 609]
   ```python
   pipeline = VTTKnowledgeExtractor(config)  # ✓ Correct orchestrator created
   ```

3. **File Discovery** [Lines 625-631]
   ```python
   vtt_files = find_vtt_files(folder, args.pattern, args.recursive)
   ```

4. **❌ BROKEN: Wrong Manager Creation** [Lines 682-686]
   ```python
   ingestion_manager = TranscriptIngestionManager(
       pipeline=pipeline,
       checkpoint=checkpoint
   )
   ```

5. **❌ BROKEN: Only VTT Parsing Called** [Lines 689-697]
   ```python
   result = ingestion_manager.process_vtt_file(vtt_file, metadata)
   ```

### Deep Dive: What TranscriptIngestionManager.process_vtt_file() Actually Does

**File**: `src/seeding/transcript_ingestion.py:394-443`

1. **Creates VTTFile Object** [Lines 408-414]
   ```python
   vtt_file_obj = self.ingestion._create_vtt_file(Path(vtt_file))
   ```

2. **Calls Basic VTT Processing** [Line 417]
   ```python
   result = self.ingestion.process_vtt_file(vtt_file_obj, self.checkpoint)
   ```

3. **TranscriptIngestion.process_vtt_file() Only Does** [Lines 180-220]:
   - ✅ Parse VTT file via `self.vtt_parser.parse_file()`
   - ✅ Merge short segments
   - ✅ Create episode metadata
   - ✅ Mark as processed in checkpoint
   - ❌ **NO KNOWLEDGE EXTRACTION**
   - ❌ **NO LLM CALLS**
   - ❌ **NO ENTITY EXTRACTION**
   - ❌ **NO NEO4J STORAGE**

### Result: Only File Parsing, No Knowledge Extraction

The current flow stops after VTT parsing and never calls the actual knowledge extraction pipeline.

## Intended Correct Execution Path

### What Should Happen After CLI Setup

1. **Configuration & Discovery** (same as current)
2. **Direct Orchestrator Call** (MISSING)
   ```python
   # Instead of TranscriptIngestionManager
   result = pipeline.process_vtt_files(vtt_files, use_large_context=True)
   ```

3. **Full Pipeline Execution** via `VTTKnowledgeExtractor.process_vtt_files()`:
   - ✅ VTT parsing via `TranscriptIngestion`
   - ✅ **Knowledge extraction via `pipeline_executor.process_vtt_segments()`**
   - ✅ **Entity resolution via provider coordinator**
   - ✅ **LLM API calls via Gemini services**
   - ✅ **Graph storage via Neo4j services**
   - ✅ Checkpoint management
   - ✅ Error handling and metrics

## Visual Flow Comparison

### Current (Broken) Flow
```
CLI process_vtt()
├── VTTKnowledgeExtractor(config)  ✓ (created but not used!)
├── TranscriptIngestionManager()   ❌ (wrong manager)
│   └── TranscriptIngestion.process_vtt_file()
│       ├── VTTParser.parse_file()           ✓ 
│       ├── merge_short_segments()           ✓
│       ├── create_episode_data()            ✓
│       └── mark_as_processed()              ✓
└── ❌ STOPS HERE - No knowledge extraction!
```

### Intended (Fixed) Flow
```
CLI process_vtt()
├── VTTKnowledgeExtractor(config)                    ✓
└── pipeline.process_vtt_files()                     ✓ (direct call)
    ├── TranscriptIngestion.process_vtt_file()       ✓ (parsing)
    └── pipeline_executor.process_vtt_segments()     ✓ (knowledge extraction)
        ├── KnowledgeExtractor.extract_knowledge()   ✓ (LLM calls)
        ├── EntityResolver.resolve_entities()        ✓ (relationships)
        └── GraphStorageService.store_to_neo4j()     ✓ (persistence)
```

## Key Architecture Problem

**The CLI creates the correct orchestrator (`VTTKnowledgeExtractor`) but never uses it!**

Instead, it creates a separate `TranscriptIngestionManager` that only does file parsing. The `VTTKnowledgeExtractor` has a perfect `process_vtt_files()` method that does exactly what we need, but the CLI bypasses it completely.

## Gap Analysis

| Component | Current Status | Should Be |
|-----------|----------------|-----------|
| **VTT Parsing** | ✅ Working | ✅ Keep |
| **Episode Metadata** | ✅ Working | ✅ Keep |
| **Checkpoint System** | ✅ Working | ✅ Keep |
| **Knowledge Extraction** | ❌ Missing | ✅ Add |
| **LLM API Calls** | ❌ Missing | ✅ Add |
| **Entity Resolution** | ❌ Missing | ✅ Add |
| **Neo4j Storage** | ❌ Missing | ✅ Add |
| **Pipeline Coordination** | ❌ Missing | ✅ Add |

## Root Cause

The CLI was designed to use a "bridge" pattern with `TranscriptIngestionManager`, but this bridge only calls the parsing layer and never the knowledge extraction layer. The architecture already exists in `VTTKnowledgeExtractor` - we just need to connect the CLI to it.

## Fix Required

**Replace lines 682-697 in CLI with a direct call to the orchestrator's `process_vtt_files()` method.**

This single change will connect the CLI to the full knowledge extraction pipeline that already exists and is properly architected.