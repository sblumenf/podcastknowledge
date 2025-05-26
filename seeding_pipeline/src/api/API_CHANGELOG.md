# API Changelog

All notable changes to the Podcast Knowledge Graph Pipeline API will be documented in this file.

The format is based on [Keep a Changelog](https://keepachangelog.com/en/1.0.0/),
and this project adheres to [Semantic Versioning](https://semver.org/spec/v2.0.0.html).

## [1.0.0] - 2024-01-01

### Added
- Initial stable API release
- `seed_podcast()` function for processing single podcasts
- `seed_podcasts()` function for batch processing
- `PodcastKnowledgePipeline` class with full control
- Version checking with `get_api_version()` and `check_api_compatibility()`
- Deprecation decorators for smooth API evolution
- Comprehensive error handling and logging
- Thread-safe operation with proper resource cleanup

### API Contract
- All functions return a standardized response dictionary
- Backward compatibility guaranteed within major version (1.x.x)
- Forward compatibility through `**kwargs` in function signatures

### Dependencies
- Requires Python >= 3.9
- Neo4j >= 5.14.0
- See requirements.txt for full list

## [1.1.0] - 2024-01-15

### Added
- Schemaless extraction mode support via `extraction_mode` parameter
- New `get_schema_evolution()` method for tracking schema changes
- Schema discovery statistics in API responses
- Flexible result types for schemaless extraction
- Backward compatible with v1.0.0 (defaults to fixed mode)

### Changed
- `seed_podcast()` and `seed_podcasts()` now accept `extraction_mode` parameter
- API responses include schemaless-specific fields when using schemaless mode

## [Unreleased]

### Planned for v1.2
- Async/await support for pipeline operations
- Streaming API for real-time processing
- Enhanced progress callbacks
- Checkpoint resume from specific episode

### Planned for v2.0
- GraphQL API endpoint
- Plugin system for custom processors
- Multi-language support
- Cloud-native deployment options