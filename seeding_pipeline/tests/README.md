# Test Suite Documentation

This directory contains the test suite for the VTT Knowledge Graph Seeding Pipeline.

## Test Structure

```
tests/
├── api/                    # API endpoint tests
├── e2e/                    # End-to-end integration tests
├── fixtures/              # Test fixtures and sample data
├── integration/           # Integration tests
├── performance/           # Performance benchmarks
├── processing/            # Knowledge extraction and processing tests
├── scripts/               # Test-related scripts
├── seeding/              # Seeding and orchestration tests
├── services/             # Service layer tests
├── unit/                 # Unit tests
├── utils/                # Utility function tests
├── conftest.py           # Pytest configuration
└── test_*.py             # Top-level test files
```

## Running Tests

### All Tests
```bash
pytest
```

### Specific Test Categories
```bash
# Unit tests only
pytest tests/unit/

# Integration tests
pytest tests/integration/

# VTT-specific tests
pytest -k "vtt"

# Neo4j tests (requires Neo4j to be running)
pytest -k "neo4j or graph"
```

### With Coverage
```bash
pytest --cov=src --cov-report=html
```

## Test Categories

### Unit Tests
- Fast, isolated tests for individual functions and classes
- Mock all external dependencies
- Located in `tests/unit/`

### Integration Tests
- Test interactions between components
- May use real services with test configurations
- Located in `tests/integration/`

### E2E Tests
- Test complete workflows from VTT input to Neo4j storage
- Located in `tests/e2e/`

### Performance Tests
- Benchmark critical operations
- Track performance regressions
- Located in `tests/performance/`

## Key Test Files

### VTT Processing
- `test_vtt_parser.py` - VTT file parsing
- `test_vtt_segmentation.py` - Transcript segmentation
- `test_vtt_extraction.py` - Knowledge extraction from VTT
- `test_vtt_pipeline_e2e.py` - Complete VTT pipeline

### Knowledge Extraction
- `test_extraction.py` - Core extraction logic
- `test_entity_resolution.py` - Entity disambiguation
- `test_parsers.py` - LLM response parsing

### Storage
- `test_graph_storage.py` - Neo4j integration
- `test_checkpoint.py` - Progress checkpointing

## Test Fixtures

Test fixtures are located in `tests/fixtures/`:
- `vtt_samples/` - Sample VTT files
- `test_podcasts.json` - Mock podcast data
- `neo4j_fixture.py` - Neo4j test container setup

## Recent Changes

As of the VTT-only pipeline cleanup:
- Removed RSS feed-related tests
- Removed audio processing tests
- Fixed import issues from refactoring
- Consolidated redundant test files
- All tests now pass without import errors

## Contributing

When adding new tests:
1. Place unit tests in `tests/unit/`
2. Place integration tests in `tests/integration/`
3. Use descriptive test names that explain what is being tested
4. Mock external dependencies in unit tests
5. Add appropriate markers (@pytest.mark.unit, @pytest.mark.integration, etc.)

## Test Coverage Goals

- Critical path coverage: >90%
- Overall coverage: >80%
- All public APIs must have tests