# Podcast Knowledge Pipeline Architecture

## Overview

This document outlines the architecture and dependency rules for the modularized podcast knowledge system, focusing exclusively on knowledge base seeding functionality.

## Dependency Analysis Results

Based on analysis of the monolithic script (8,179 lines):

### External Dependencies

**Core Requirements:**
- `neo4j` - Graph database driver (required)
- `torch` - PyTorch for ML models
- `faster-whisper` or `openai-whisper` - Audio transcription
- `pyannote.audio` - Speaker diarization
- `langchain`, `langchain-google-genai` - LLM integration
- `sentence-transformers` - Embeddings (inferred from usage)
- `feedparser` - RSS feed parsing
- `python-dotenv` - Environment variable management

**Scientific Computing:**
- `numpy` - Numerical operations
- `scipy` - Statistical functions
- `networkx` - Graph algorithms

**Utilities:**
- `tqdm` - Progress tracking

**NOT MIGRATED (Visualization):**
- `matplotlib` - Chart generation (removed)
- All visualization-related code

### Internal Class Dependencies

```
PodcastKnowledgePipeline
    ├── AudioProcessor
    ├── EnhancedPodcastSegmenter
    ├── GraphOperations
    │   └── Neo4jManager
    ├── TaskRouter
    ├── RelationshipExtractor
    ├── ExtractionValidator
    ├── VectorEntityMatcher
    ├── OptimizedPatternMatcher
    ├── HybridRateLimiter
    └── ProgressCheckpoint

Configuration Hierarchy:
    PodcastConfig
        └── SeedingConfig

Exception Hierarchy:
    PodcastProcessingError
        ├── DatabaseConnectionError
        ├── AudioProcessingError
        ├── LLMProcessingError
        └── ConfigurationError
```

## Module Boundaries

### 1. Core Module (`src/core/`)
- **Purpose**: Foundational interfaces, models, and configuration
- **No dependencies on**: Any other internal modules
- **Contains**: Interfaces, data models, exceptions, config

### 2. Providers Module (`src/providers/`)
- **Purpose**: External service integrations
- **Depends on**: Core only
- **Contains**: Audio, LLM, Graph, Embedding providers
- **Key principle**: Each provider implements a core interface

### 3. Processing Module (`src/processing/`)
- **Purpose**: Business logic for knowledge extraction
- **Depends on**: Core, Providers
- **Contains**: Extraction, segmentation, entity resolution, metrics
- **Not allowed**: Direct external API calls (must use providers)

### 4. Utils Module (`src/utils/`)
- **Purpose**: Shared utilities
- **Depends on**: Core only
- **Contains**: Pattern matching, memory management, retry logic
- **Key principle**: No business logic, only technical utilities

### 5. Seeding Module (`src/seeding/`)
- **Purpose**: Pipeline orchestration
- **Depends on**: All other modules
- **Contains**: Orchestrator, checkpoint management, batch processing
- **Key principle**: This is the only module that ties everything together

## Circular Dependency Prevention Rules

1. **Strict Layering**: Dependencies flow in one direction:
   ```
   Seeding → Processing → Providers → Core
                ↓
              Utils
   ```

2. **Interface Segregation**: Providers communicate through interfaces defined in Core

3. **No Cross-Provider Dependencies**: Providers cannot depend on each other

4. **Utils Independence**: Utils can only depend on Core, nothing depends on specific utils

## Migration Strategy

### Phase 1: Core Foundation
Extract in order:
1. Exceptions (no dependencies)
2. Models (no dependencies) 
3. Interfaces (depends on models)
4. Configuration (depends on models)

### Phase 2: Providers
Extract independently:
1. Audio provider (implements interface)
2. LLM provider (implements interface)
3. Graph provider (implements interface)
4. Embedding provider (implements interface)

### Phase 3: Processing
Extract with provider dependencies:
1. Segmentation (uses providers)
2. Extraction (uses providers)
3. Entity resolution (uses providers)
4. Metrics (uses providers)

### Phase 4: Orchestration
Extract last:
1. Checkpoint management
2. Batch processing
3. Main orchestrator

## Design Decisions

1. **Provider Pattern**: All external dependencies wrapped in providers for testability
2. **Dependency Injection**: Orchestrator receives providers, doesn't create them
3. **Configuration Hierarchy**: SeedingConfig extends PodcastConfig for backward compatibility
4. **No Visualization**: All matplotlib and visualization code removed per requirements
5. **Batch-First Design**: Optimized for unattended processing, not interactive use

## Risk Mitigation

1. **Gradual Migration**: Each module can be tested independently
2. **Interface Stability**: Core interfaces defined first and frozen early
3. **Backward Compatibility**: Configuration structure preserved where possible
4. **Test Coverage**: Each module must have unit tests before integration