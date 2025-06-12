# Critical Path Test Coverage

## Overview

This document describes the minimal but functional test suite for the VTT → Neo4j pipeline, designed to support batch processing of hundreds of episodes with basic error recovery.

## What's Tested ✅

### 1. **Neo4j Storage Operations** (`test_neo4j_critical_path.py`)
- Creating Episode nodes with properties
- Creating Segment nodes and relationships
- Handling duplicate episodes
- Transaction rollback on errors
- Connection failure handling
- Automatic reconnection after connection loss

### 2. **VTT File Processing** (`test_vtt_processing.py`)
- Parsing real VTT files (standard format)
- Handling corrupt VTT files
- Processing empty VTT files
- Performance with large VTT files (1000 segments)
- Special characters and Unicode handling
- Multi-line segment support

### 3. **Knowledge Extraction** (`test_vtt_processing.py`)
- Basic knowledge extraction from segments
- Entity deduplication
- Relationship extraction (with mocked LLM)
- Empty/short segment handling

### 4. **End-to-End Pipeline** (`test_e2e_critical_path.py`)
- Complete VTT → Knowledge Extraction → Neo4j flow
- Batch processing of multiple files
- Mixed success/failure handling
- Checkpoint recovery between runs

### 5. **Performance Baselines** (`test_baseline_performance.py`)
- Single file processing time (< 5 seconds)
- Batch processing throughput (files/second)
- Memory usage monitoring
- Performance metrics saved to baseline files

## What's NOT Tested ❌

- Complex extraction scenarios with real LLM services
- Large scale performance (1000+ files)
- Concurrent processing with multiple workers
- Advanced error recovery scenarios
- Data quality validation
- Real-world VTT format variations
- Authentication and authorization
- API endpoints (if any)
- Complex relationship graph queries

## Running Tests

### Prerequisites
- Docker must be running (for Neo4j containers)
- Python 3.11 with virtual environment activated
- All dependencies installed: `pip install -r requirements-dev.txt`

### Run All Critical Path Tests
```bash
# Using the test runner script (recommended)
./scripts/run_critical_tests.py

# Run with performance tests
./scripts/run_critical_tests.py --all

# Using pytest directly
pytest -v -m integration tests/integration/
```

### Run Specific Test Categories
```bash
# Neo4j storage tests only
pytest tests/integration/test_neo4j_critical_path.py -v

# VTT processing tests only
pytest tests/integration/test_vtt_processing.py -v

# E2E pipeline tests only
pytest tests/integration/test_e2e_critical_path.py -v

# Performance tests only
pytest -v -m performance tests/performance/
```

### CI/CD Integration
Tests run automatically on:
- Every push to `main` or `develop` branches
- Every pull request to `main`
- Performance tests run only on pushes to `main`

## Known Limitations

1. **Mocked LLM Service**: Tests use simplified mocks for LLM interactions to avoid API costs and ensure deterministic results

2. **Small Test Files**: Performance tests use small VTT files that may not reflect real-world processing times

3. **No Stress Testing**: Current tests don't push the system to its limits or test resource exhaustion

4. **Limited Neo4j Queries**: Tests focus on basic CRUD operations, not complex graph traversals

5. **No Integration with External Services**: Tests don't cover integration with external APIs or services

## Troubleshooting

### Docker Issues
```bash
# Check if Docker is running
docker ps

# Start Docker daemon (Linux)
sudo systemctl start docker

# Start Docker Desktop (Mac/Windows)
# Open Docker Desktop application
```

### Neo4j Container Issues
```bash
# Check container logs
docker logs $(docker ps -q --filter ancestor=neo4j:5.14.0)

# Manually start Neo4j container for debugging
docker run -p 7687:7687 -e NEO4J_AUTH=neo4j/testpassword neo4j:5.14.0
```

### Test Timeout Issues
- Increase timeout in pytest: `pytest --timeout=600`
- Check system resources (CPU, memory, disk)
- Ensure no other Neo4j instances are running on port 7687

## Next Steps for Expanding Tests

1. **Add Real LLM Integration Tests** (with test API keys)
   - Test actual entity extraction quality
   - Validate relationship discovery
   - Measure extraction accuracy

2. **Implement Stress Tests**
   - Process 100+ files concurrently
   - Test memory limits
   - Measure system breaking points

3. **Add Data Quality Tests**
   - Validate extracted entities make sense
   - Check for data consistency
   - Verify graph structure integrity

4. **Create Integration Test Suite**
   - Test with real podcast data
   - Validate against expected outputs
   - Measure end-to-end accuracy

5. **Add Monitoring Tests**
   - Test logging functionality
   - Verify metrics collection
   - Check error reporting

## Success Metrics

Current implementation achieves:
- ✅ < 10 import errors (achieved: 0)
- ✅ Full VTT → Neo4j pipeline coverage
- ✅ Batch processing with error handling
- ✅ Basic checkpoint recovery
- ✅ Performance baselines established
- ✅ Automated CI/CD pipeline
- ✅ Clear documentation

This minimal test suite provides confidence that the core pipeline works while keeping complexity and maintenance burden low.