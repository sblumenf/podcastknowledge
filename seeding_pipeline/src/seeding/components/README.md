# Seeding Pipeline Components

This directory contains the modular components extracted from the monolithic orchestrator during Phase 2 of the refactoring plan.

## Components

### SignalManager
Handles graceful shutdown via SIGINT and SIGTERM signals.

### ProviderCoordinator
Manages initialization, health checks, and cleanup of all providers (audio, LLM, graph, embeddings) and processing components.

### CheckpointManager
Wraps checkpoint functionality for episode progress tracking and schema discovery in schemaless mode.

### PipelineExecutor
Contains the core pipeline execution logic for processing podcast episodes. Supports fixed schema, schemaless, and migration modes.

### StorageCoordinator
Handles all graph database storage operations including entities, relationships, insights, quotes, and emergent themes.

## Design Principles

1. **Single Responsibility**: Each component has one clear purpose
2. **Dependency Injection**: Components receive dependencies through constructors
3. **Interface Preservation**: Public APIs remain unchanged
4. **Backward Compatibility**: All existing functionality preserved

## Usage

These components are used internally by the `PodcastKnowledgePipeline` orchestrator. The orchestrator acts as a facade, delegating operations to the appropriate components while maintaining the original public interface.

## Future Enhancements

- Provider plugin system (Phase 3)
- Extraction strategy pattern (Phase 4)
- Additional performance optimizations