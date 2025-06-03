# Embedding Service Usage Map

## Overview
This document maps all usage of the embedding service throughout the codebase. The current implementation uses sentence-transformers with the `all-MiniLM-L6-v2` model (384 dimensions).

## Core Interfaces

### EmbeddingProvider Protocol
**Location**: `src/core/interfaces.py:195-229`
- Methods:
  - `generate_embedding(text: str) -> List[float]`
  - `generate_embeddings_batch(texts: List[str]) -> List[List[float]]`
  - `get_embedding_dimension() -> int`
  - Inherits from `HealthCheckable` protocol

## Current Implementation

### EmbeddingsService
**Location**: `src/services/embeddings.py`
- Model: `all-MiniLM-L6-v2`
- Default dimension: 384
- Device: CPU by default
- Features:
  - Single and batch embedding generation
  - Similarity computation
  - Finding similar embeddings
  - Empty text handling (returns zero vector)

## Usage Points

### 1. Core Service Files
- **src/services/__init__.py**: Exports EmbeddingsService
- **src/services/embeddings.py**: Main implementation (13-219)

### 2. Orchestration Layer
- **src/seeding/orchestrator.py**: Uses embeddings service in processing pipeline
- **src/seeding/components/provider_coordinator.py**: Coordinates embedding provider

### 3. Processing Components
- **src/processing/episode_flow.py**: May use embeddings for episode processing
- **src/extraction/importance_scoring.py**: May use embeddings for scoring

### 4. Configuration
- **src/core/config.py**: Contains embedding configuration (model name, dimensions)

### 5. Test Files Using Embeddings
- **tests/services/test_embeddings_service.py**: Direct service tests
- **tests/unit/test_interfaces_full.py**: Interface compliance tests
- **tests/unit/test_orchestrator_unit.py**: Orchestrator tests with embeddings
- **tests/integration/test_vtt_e2e.py**: End-to-end tests
- **tests/processing/test_entity_resolution.py**: Entity resolution with embeddings
- **tests/processing/test_importance_scoring.py**: Importance scoring tests
- **tests/performance/benchmark_schemaless.py**: Performance benchmarks

### 6. Mock/Test Utilities
- **tests/utils/external_service_mocks.py**: Mock embedding service
- **tests/utils/test_helpers.py**: Test utilities for embeddings

### 7. Scripts and Examples
- **scripts/validation/validate_providers.py**: Provider validation including embeddings
- **docs/examples/provider_examples.py**: Example usage of embedding provider
- **docs/examples/processing_examples.py**: Processing examples with embeddings

## Dimension Dependencies

### Hardcoded Dimensions (384)
The following files contain references to the 384-dimension value:
- Multiple test files assume 384 dimensions
- Config files may have default dimension settings

### Model References (all-MiniLM-L6-v2)
Files referencing the specific model:
- `src/services/embeddings.py`: Default model in constructor
- Various test files
- Configuration examples

## Integration Points

### 1. Provider Coordinator
The embedding service is integrated through the provider coordinator pattern, allowing for flexible provider switching.

### 2. Health Checks
Embedding service implements health checks as part of the HealthCheckable protocol.

### 3. Error Handling
Uses ProviderError for consistent error handling across the system.

## Key Methods Used

1. **generate_embedding(text: str)**: Single text embedding
2. **generate_embeddings(texts: List[str])**: Batch processing
3. **compute_similarity(embedding1, embedding2)**: Cosine similarity
4. **find_similar(query_embedding, embeddings, top_k)**: Similarity search
5. **get_model_info()**: Model metadata

## Configuration Variables

- Model name: Configurable, defaults to `all-MiniLM-L6-v2`
- Embedding dimension: 384 (for current model)
- Device: CPU/CUDA selection
- Batch size: 32 (default)
- Normalize embeddings: True (default)

## Notes for Migration

1. **Dimension Change**: Moving from 384 (MiniLM) to 768 (text-embedding-004) dimensions
2. **API vs Local**: Switching from local model to API-based generation
3. **Batch Processing**: Need to handle API rate limits for batch operations
4. **Error Handling**: Different error types (network/API vs model errors)
5. **Cost Implications**: API calls have associated costs unlike local model