# Infrastructure Requirements for Testing

This document outlines the infrastructure and service dependencies required to run the complete test suite for the Podcast Knowledge Graph Pipeline.

## Summary

The test suite has been designed with infrastructure-aware testing in mind. Tests are categorized by their infrastructure requirements, allowing you to run subsets of tests based on what services are available.

## Test Categories

### 1. Unit Tests (No Infrastructure Required)
- **Marker**: `@pytest.mark.unit`
- **Run Command**: `pytest -m "unit and not requires_neo4j and not requires_gpu and not requires_api_keys"`
- **Requirements**: None (pure Python)
- **Coverage Impact**: ~15-20%

### 2. Mock-Based Tests (No Infrastructure Required)
- **Marker**: Implicitly included in unit tests
- **Run Command**: `pytest tests/unit`
- **Requirements**: None (uses mock objects)
- **Coverage Impact**: ~20-25%

### 3. Integration Tests (Infrastructure Required)

#### Neo4j Database
- **Marker**: `@pytest.mark.requires_neo4j`
- **Service**: Neo4j 4.4+ 
- **Setup**:
  ```bash
  # Using Docker
  docker run -d \
    --name neo4j-test \
    -p 7688:7687 \
    -e NEO4J_AUTH=neo4j/testpassword \
    neo4j:4.4
  ```
- **Cost**: ~$50-100/month for cloud instance
- **Tests Affected**: 33 test files
- **Coverage Impact**: +15-20%

#### GPU Support (Whisper)
- **Marker**: `@pytest.mark.requires_gpu`
- **Requirements**: CUDA-capable GPU
- **Setup**: Install CUDA toolkit and PyTorch with GPU support
- **Cost**: ~$100-500/month for cloud GPU instance
- **Tests Affected**: 4 test files
- **Coverage Impact**: +5%

#### External API Keys
- **Marker**: `@pytest.mark.requires_api_keys`
- **Services**:
  - Google Gemini API (GOOGLE_API_KEY)
  - OpenAI API (OPENAI_API_KEY) 
  - Hugging Face (HF_TOKEN)
- **Cost**: Variable based on usage ($10-100/month)
- **Tests Affected**: 5 test files
- **Coverage Impact**: +10%

#### Docker
- **Marker**: `@pytest.mark.requires_docker`
- **Service**: Docker Engine
- **Setup**: Install Docker Desktop or Docker Engine
- **Cost**: Free (local) or included in cloud instance
- **Tests Affected**: Integration tests using docker-compose
- **Coverage Impact**: +10%

### 4. End-to-End Tests
- **Marker**: `@pytest.mark.e2e`
- **Requirements**: All of the above
- **Coverage Impact**: +10-15%

## Progressive Testing Strategy

### Phase 1: Local Development (No Cost)
```bash
# Run only unit tests without infrastructure
pytest -m "unit and not requires_neo4j and not requires_gpu and not requires_api_keys"
```
Expected Coverage: ~20-25%

### Phase 2: Add Mock Services (No Cost)
```bash
# Run all unit tests including those with mocked services
pytest tests/unit -v
```
Expected Coverage: ~25-30%

### Phase 3: Add Neo4j (Low Cost)
```bash
# Start Neo4j locally with Docker
docker-compose -f tests/integration/docker-compose.test.yml up -d neo4j

# Run tests including Neo4j
pytest -m "not requires_gpu and not requires_api_keys"
```
Expected Coverage: ~40-50%

### Phase 4: Add API Keys (Medium Cost)
```bash
# Set up test API keys with low quotas
export GOOGLE_API_KEY="your-test-key"
export OPENAI_API_KEY="your-test-key"

# Run all non-GPU tests
pytest -m "not requires_gpu"
```
Expected Coverage: ~60-70%

### Phase 5: Full Infrastructure (High Cost)
```bash
# With GPU instance and all services
pytest
```
Expected Coverage: ~90%

## Cost Optimization Tips

1. **Use GitHub Actions Free Tier**
   - 2,000 minutes/month for private repos
   - Run unit tests on every push
   - Run integration tests on PR/merge only

2. **Local Development First**
   - Use mocks extensively
   - Run full suite only before releases
   - Cache test results

3. **Shared Test Infrastructure**
   - Use a shared Neo4j test instance
   - Pool API keys with rate limiting
   - Schedule GPU tests for off-peak hours

4. **Test Data Management**
   - Use small test datasets
   - Cache transcription results
   - Mock expensive operations

## Environment Variables

Create a `.env.test` file with:

```bash
# Required for all tests
PYTHONPATH=./src:$PYTHONPATH

# Neo4j (when available)
NEO4J_URI=bolt://localhost:7688
NEO4J_USERNAME=neo4j
NEO4J_PASSWORD=testpassword

# API Keys (when available)
GOOGLE_API_KEY=test-key-with-limits
OPENAI_API_KEY=test-key-with-limits
HF_TOKEN=test-token

# Optional
LOG_LEVEL=WARNING
TEST_TIMEOUT=30
```

## Running Tests by Infrastructure

### No Infrastructure
```bash
# Quick validation
pytest tests/unit/test_config.py tests/unit/test_models.py -v

# All pure unit tests
pytest -m "unit" -k "not neo4j and not gpu and not api" -v
```

### With Neo4j Only
```bash
# Start Neo4j
docker run -d --name neo4j-test -p 7688:7687 -e NEO4J_AUTH=neo4j/test neo4j:4.4

# Run tests
pytest -m "unit or requires_neo4j" -k "not gpu and not api" -v
```

### Progressive Coverage Targets

| Phase | Infrastructure | Cost/Month | Coverage Target | Time to Run |
|-------|---------------|------------|-----------------|-------------|
| 1 | None | $0 | 20% | 2 min |
| 2 | Mocks | $0 | 30% | 5 min |
| 3 | +Neo4j | $50 | 50% | 10 min |
| 4 | +APIs | $100 | 70% | 15 min |
| 5 | +GPU | $300 | 90% | 30 min |

## Next Steps

1. Start with Phase 1 (no infrastructure)
2. Fix failing unit tests
3. Add markers to existing tests
4. Gradually add infrastructure as needed
5. Monitor costs and optimize usage