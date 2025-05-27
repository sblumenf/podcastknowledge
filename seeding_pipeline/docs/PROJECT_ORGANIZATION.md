# Project Organization Guide

This document explains the structure and organization of the Podcast Knowledge Graph Pipeline after the cleanup performed on May 27, 2025.

## Directory Structure Overview

```
seeding_pipeline/
├── src/                    # Source code - clean, production-ready modules
├── tests/                  # All test code, organized by type
├── scripts/                # Utility scripts, organized by purpose
├── docs/                   # Documentation, streamlined and organized
├── config/                 # Configuration files with examples
├── notebooks/              # Jupyter notebooks for analysis
├── monitoring/             # Monitoring and observability configuration
├── k8s/                    # Kubernetes deployment manifests
├── docker/                 # Docker configuration
└── examples/               # Usage examples
```

## Key Directories Explained

### `/src` - Source Code
The core application code, organized by functionality:
- **`/api`**: RESTful API implementation (FastAPI)
- **`/core`**: Core models, interfaces, and configuration
- **`/factories`**: Factory pattern implementations for providers
- **`/processing`**: Business logic for extraction, segmentation, analysis
- **`/providers`**: Pluggable providers for audio, LLM, graph, embeddings
- **`/seeding`**: Pipeline orchestration and batch processing
- **`/utils`**: Utility functions and helpers
- **`/tracing`**: Distributed tracing implementation
- **`/migration`**: Schema and data migration tools

### `/tests` - Test Suite
Comprehensive test coverage:
- **`/unit`**: Unit tests for individual components
- **`/integration`**: Integration tests with real services
- **`/e2e`**: End-to-end pipeline tests
- **`/performance`**: Performance benchmarks
- **`/scripts`**: Test scripts moved from scripts/ directory

### `/scripts` - Organized Utilities
Scripts organized by purpose:
- **`/validation`**: All validation and audit scripts
- **`/benchmarks`**: Performance benchmarking scripts
- **`/migration`**: Migration utility scripts
- Other utility scripts at root level

### `/docs` - Streamlined Documentation
- **`/architecture`**: Core architectural decisions and design docs
- **`/guides`**: User and developer guides
- **`/api`**: API documentation and OpenAPI specs
- **`/runbooks`**: Operational procedures
- **`/archive`**: Historical documents from refactoring
  - `/refactor-history`: Phase 1-9 documentation
  - `/status-reports`: Completion and validation reports
  - `/deprecated`: Old implementations and POCs

### `/config` - Configuration
- Active configuration files at root
- **`/examples`**: Example configurations for reference
- Clear naming: `config.example.yml`, `schemaless.example.yml`

## Provider Organization

Each provider type follows a consistent structure:
```
providers/
├── audio/
│   ├── base.py          # Abstract base class
│   ├── whisper.py       # OpenAI Whisper implementation
│   └── mock.py          # Mock for testing
├── llm/
│   ├── base.py          # Abstract base class
│   ├── gemini.py        # Google Gemini implementation
│   ├── gemini_adapter.py # Adapter for GraphRAG
│   └── mock.py          # Mock for testing
├── graph/
│   ├── base.py          # Abstract base class
│   ├── neo4j.py         # Default Neo4j implementation
│   ├── schemaless_neo4j.py # Schemaless extraction
│   ├── compatible_neo4j.py # Migration compatibility
│   └── README.md        # Implementation guide
└── embeddings/
    ├── base.py          # Abstract base class
    ├── sentence_transformer.py # SentenceTransformers
    └── mock.py          # Mock for testing
```

## Cleanup Summary

### What Was Changed
1. **Archived 50+ historical documents** from the refactoring process
2. **Organized scripts** into logical subdirectories
3. **Removed POC files** that were only used for testing
4. **Consolidated duplicate files** (mock providers, migration docs)
5. **Updated code** to handle flexible configuration paths
6. **Created documentation** for provider implementations

### What Wasn't Changed
- Core functionality remains intact
- All imports and dependencies work as before
- API contracts are unchanged
- Configuration structure is preserved

## Configuration Management

The system now supports flexible configuration through:
- Environment variable: `PODCAST_KG_CONFIG_DIR`
- Default fallback to `config/` directory
- Automatic path resolution for different deployment scenarios

## Best Practices

1. **Adding New Features**: Follow the provider pattern in `/src/providers`
2. **Writing Tests**: Mirror the source structure in `/tests`
3. **Documentation**: Keep user docs in `/docs/guides`, API docs in `/docs/api`
4. **Scripts**: Place validation scripts in `/scripts/validation`, benchmarks in `/scripts/benchmarks`

## Migration Notes

If you're updating from a previous version:
1. Update any scripts that imported from `schemaless_poc`
2. Check for hardcoded config paths and update if needed
3. Review the `/docs/archive` for historical context if needed

The cleanup has significantly improved project navigation while maintaining full backward compatibility.