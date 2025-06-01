# Minimal Critical Path Testing Implementation Plan

**Created**: 2025-01-06  
**Purpose**: Establish minimal but functional test suite for VTT → Neo4j pipeline to support batch processing of hundreds of episodes

## Executive Summary

This plan creates a minimal test suite focused exclusively on the critical path: processing VTT files through knowledge extraction into Neo4j storage. The approach prioritizes functionality over coverage, ensuring the system can reliably process batches of hundreds of episodes with basic error recovery. We will delete non-functional tests, implement container-based Neo4j testing, and create focused integration tests that validate actual data flow.

## Phase 1: Clean Test Environment

### Task 1.1: Remove Non-Functional Tests
- [x] Delete tests for non-existent modules
  - Purpose: Remove noise and false failures from test suite
  - Steps:
    1. Use context7 MCP tool to review file deletion best practices
    2. Create backup: `tar -czf tests_backup_$(date +%Y%m%d).tar.gz tests/`
    3. Delete test files with missing module imports:
       ```bash
       rm tests/processing/test_complexity_analysis.py
       rm tests/processing/test_discourse_flow.py
       rm tests/processing/test_emergent_themes.py
       rm tests/processing/test_graph_analysis.py
       rm tests/unit/test_error_budget.py
       ```
    4. Delete tests for removed features:
       ```bash
       rm tests/integration/test_api_contracts.py
       rm tests/integration/test_minimal_schemaless.py
       rm tests/integration/test_schemaless_pipeline.py
       rm tests/performance/test_domain_diversity.py
       ```
    5. Update `test_tracking/deleted_tests.log` with removal reasons
  - Validation: `pytest --collect-only` shows < 20 import errors

### Task 1.2: Setup Test Infrastructure
- [x] Install container testing dependencies
  - Purpose: Enable Neo4j container-based testing
  - Steps:
    1. Use context7 MCP tool to review testcontainers documentation
    2. Add to requirements-dev.txt:
       ```
       testcontainers[neo4j]==3.7.1
       pytest-timeout==2.2.0
       pytest-xdist==3.5.0
       ```
    3. Run: `pip install -r requirements-dev.txt`
    4. Verify Docker available: `docker --version`
    5. Test container startup: `python -c "from testcontainers.neo4j import Neo4jContainer"`
  - Validation: Dependencies installed without errors

### Task 1.3: Create Test Configuration
- [x] Setup centralized test configuration
  - Purpose: Consistent test environment settings
  - Steps:
    1. Use context7 MCP tool to review pytest configuration best practices
    2. Create `tests/conftest.py`:
       ```python
       import pytest
       import tempfile
       from pathlib import Path
       
       @pytest.fixture(scope="session")
       def test_data_dir():
           """Provide test data directory."""
           return Path(__file__).parent / "fixtures" / "vtt_samples"
       
       @pytest.fixture(scope="function")
       def temp_dir():
           """Provide temporary directory for test outputs."""
           with tempfile.TemporaryDirectory() as tmpdir:
               yield Path(tmpdir)
       ```
    3. Create `tests/pytest.ini`:
       ```ini
       [pytest]
       testpaths = tests
       python_files = test_*.py
       python_classes = Test*
       python_functions = test_*
       addopts = -v --tb=short --strict-markers
       markers =
           integration: Integration tests requiring external services
           slow: Tests that take > 1 second
       ```
    4. Create placeholder for Neo4j fixture (implemented in Phase 2)
  - Validation: `pytest --collect-only` recognizes configuration

## Phase 2: Neo4j Integration Testing

### Task 2.1: Implement Neo4j Test Container
- [x] Create Neo4j container fixture
  - Purpose: Provide isolated Neo4j instance for testing
  - Steps:
    1. Use context7 MCP tool to review Neo4j testcontainers examples
    2. Create `tests/fixtures/neo4j_fixture.py`:
       ```python
       import pytest
       from testcontainers.neo4j import Neo4jContainer
       from neo4j import GraphDatabase
       
       @pytest.fixture(scope="module")
       def neo4j_container():
           """Provide Neo4j container for testing."""
           container = Neo4jContainer("neo4j:5.14.0")
           container.start()
           yield container
           container.stop()
       
       @pytest.fixture(scope="function")
       def neo4j_driver(neo4j_container):
           """Provide Neo4j driver with clean database."""
           driver = GraphDatabase.driver(
               neo4j_container.get_connection_url(),
               auth=("neo4j", neo4j_container.ADMIN_PASSWORD)
           )
           # Clear database before each test
           with driver.session() as session:
               session.run("MATCH (n) DETACH DELETE n")
           yield driver
           driver.close()
       ```
    3. Add error handling for container startup failures
    4. Add logging for debugging container issues
  - Validation: Container starts and provides working driver

### Task 2.2: Create Neo4j Storage Tests
- [x] Test basic Neo4j operations
  - Purpose: Validate storage layer functionality
  - Steps:
    1. Use context7 MCP tool to review Neo4j Python driver best practices
    2. Create `tests/integration/test_neo4j_critical_path.py`:
       ```python
       import pytest
       from src.storage.graph_storage import GraphStorageService
       from src.core.models import Episode, Segment
       
       @pytest.mark.integration
       class TestNeo4jCriticalPath:
           def test_store_episode(self, neo4j_driver):
               """Test storing episode in Neo4j."""
               storage = GraphStorageService(driver=neo4j_driver)
               episode = Episode(
                   id="test-ep-001",
                   title="Test Episode",
                   description="Test description",
                   published_date="2025-01-06",
                   duration=3600
               )
               
               # Store episode
               result = storage.store_episode(episode)
               
               # Verify stored
               with neo4j_driver.session() as session:
                   count = session.run(
                       "MATCH (e:Episode {id: $id}) RETURN count(e) as count",
                       id=episode.id
                   ).single()["count"]
                   assert count == 1
       ```
    3. Add test for storing segments with relationships
    4. Add test for handling duplicate episodes
    5. Add test for transaction rollback on error
  - Validation: All storage tests pass

### Task 2.3: Test Error Recovery
- [x] Validate error handling in storage layer
  - Purpose: Ensure system can recover from storage failures
  - Steps:
    1. Use context7 MCP tool to review error handling test patterns
    2. Add to `test_neo4j_critical_path.py`:
       ```python
       def test_storage_connection_failure(self):
           """Test handling of connection failures."""
           # Create storage with bad connection
           storage = GraphStorageService(
               uri="bolt://nonexistent:7687",
               username="neo4j",
               password="wrong"
           )
           
           episode = Episode(id="test", title="Test", 
                           description="Test", published_date="2025-01-06")
           
           # Should not crash, but return error
           with pytest.raises(ConnectionError):
               storage.store_episode(episode)
       
       def test_transaction_rollback(self, neo4j_driver):
           """Test transaction rollback on error."""
           storage = GraphStorageService(driver=neo4j_driver)
           
           # This should fail and rollback
           with pytest.raises(Exception):
               storage.store_knowledge_graph(
                   episode_id="test",
                   entities=[{"id": None}]  # Invalid entity
               )
           
           # Verify nothing was stored
           with neo4j_driver.session() as session:
               count = session.run("MATCH (n) RETURN count(n) as count").single()["count"]
               assert count == 0
       ```
    3. Add timeout handling test
    4. Add connection retry test
  - Validation: Error scenarios handled gracefully

## Phase 3: VTT Processing Tests

### Task 3.1: Validate VTT Parser
- [x] Ensure VTT parser handles real-world files
  - Purpose: Confirm parser works with actual VTT formats
  - Steps:
    1. Use context7 MCP tool to review VTT specification
    2. Create `tests/integration/test_vtt_processing.py`:
       ```python
       import pytest
       from pathlib import Path
       from src.vtt.vtt_parser import VTTParser
       
       class TestVTTProcessing:
           def test_parse_real_vtt_file(self, test_data_dir):
               """Test parsing actual VTT file."""
               parser = VTTParser()
               vtt_file = test_data_dir / "standard.vtt"
               
               segments = parser.parse_file(vtt_file)
               
               assert len(segments) > 0
               assert all(s.text for s in segments)
               assert all(s.start_time < s.end_time for s in segments)
           
           def test_parse_corrupt_vtt(self, temp_dir):
               """Test handling of corrupt VTT."""
               corrupt_file = temp_dir / "corrupt.vtt"
               corrupt_file.write_text("NOT A VALID VTT FILE")
               
               parser = VTTParser()
               with pytest.raises(ValidationError):
                   parser.parse_file(corrupt_file)
       ```
    3. Add test for empty VTT files
    4. Add test for very large VTT files (performance)
    5. Add test for special characters in text
  - Validation: Parser handles various VTT formats

### Task 3.2: Test Knowledge Extraction
- [x] Validate extraction produces usable results
  - Purpose: Ensure extraction generates valid knowledge graph data
  - Steps:
    1. Use context7 MCP tool to review extraction patterns
    2. Add to `test_vtt_processing.py`:
       ```python
       def test_extract_knowledge_from_segment(self):
           """Test knowledge extraction from parsed segment."""
           from src.extraction.extraction import KnowledgeExtractor
           from src.core.models import Segment
           
           # Mock LLM service
           class MockLLM:
               def generate(self, *args, **kwargs):
                   return {"entities": [], "relationships": []}
           
           extractor = KnowledgeExtractor(llm_service=MockLLM())
           segment = Segment(
               id="test-001",
               text="Dr. Smith from MIT discusses artificial intelligence.",
               start_time=0.0,
               end_time=10.0
           )
           
           result = extractor.extract_knowledge(segment)
           
           assert result is not None
           assert hasattr(result, 'entities')
           assert hasattr(result, 'relationships')
       ```
    3. Add test for entity deduplication
    4. Add test for relationship extraction
    5. Add test for empty/short segments
  - Validation: Extraction produces valid results

## Phase 4: End-to-End Pipeline Testing

### Task 4.1: Create Full Pipeline Test
- [x] Test complete VTT → Neo4j flow
  - Purpose: Validate entire processing pipeline works
  - Steps:
    1. Use context7 MCP tool to review integration testing patterns
    2. Create `tests/integration/test_e2e_critical_path.py`:
       ```python
       import pytest
       from pathlib import Path
       from src.seeding.orchestrator import VTTKnowledgeExtractor
       
       @pytest.mark.integration
       @pytest.mark.slow
       class TestE2ECriticalPath:
           def test_vtt_to_neo4j_pipeline(self, test_data_dir, neo4j_driver, temp_dir):
               """Test complete pipeline from VTT to Neo4j."""
               # Create orchestrator with test config
               config = {
                   "neo4j_driver": neo4j_driver,
                   "checkpoint_dir": temp_dir / "checkpoints"
               }
               orchestrator = VTTKnowledgeExtractor(config=config)
               
               # Process single VTT file
               vtt_file = test_data_dir / "minimal.vtt"
               result = orchestrator.process_vtt_files([vtt_file])
               
               # Verify processing succeeded
               assert result["processed"] == 1
               assert result["failed"] == 0
               
               # Verify data in Neo4j
               with neo4j_driver.session() as session:
                   episode_count = session.run(
                       "MATCH (e:Episode) RETURN count(e) as count"
                   ).single()["count"]
                   assert episode_count == 1
                   
                   segment_count = session.run(
                       "MATCH (s:Segment) RETURN count(s) as count"
                   ).single()["count"]
                   assert segment_count > 0
       ```
    3. Add test for batch processing multiple files
    4. Add test for checkpoint recovery
    5. Add test for handling mixed success/failure
  - Validation: Pipeline processes files end-to-end

### Task 4.2: Test Batch Processing
- [x] Validate batch processing capabilities
  - Purpose: Ensure system can handle hundreds of files
  - Steps:
    1. Use context7 MCP tool to review batch testing strategies
    2. Add to `test_e2e_critical_path.py`:
       ```python
       def test_batch_processing(self, test_data_dir, neo4j_driver, temp_dir):
           """Test processing batch of files."""
           # Create test batch (use same file multiple times)
           vtt_file = test_data_dir / "minimal.vtt"
           batch = [vtt_file] * 10  # Simulate 10 files
           
           orchestrator = VTTKnowledgeExtractor(config={
               "neo4j_driver": neo4j_driver,
               "checkpoint_dir": temp_dir / "checkpoints",
               "batch_size": 5
           })
           
           result = orchestrator.process_vtt_files(batch)
           
           assert result["processed"] == 10
           assert result["checkpoint_saved"] == True
       
       def test_batch_with_failures(self, test_data_dir, neo4j_driver, temp_dir):
           """Test batch processing with some failures."""
           good_file = test_data_dir / "minimal.vtt"
           bad_file = temp_dir / "nonexistent.vtt"
           
           batch = [good_file, bad_file, good_file]
           
           orchestrator = VTTKnowledgeExtractor(config={
               "neo4j_driver": neo4j_driver,
               "checkpoint_dir": temp_dir / "checkpoints"
           })
           
           result = orchestrator.process_vtt_files(batch)
           
           assert result["processed"] == 2
           assert result["failed"] == 1
           assert bad_file.name in result["failed_files"]
       ```
    3. Add test for checkpoint recovery mid-batch
    4. Add test for memory usage with large batches
  - Validation: Batch processing handles success and failures

### Task 4.3: Performance Baseline Test
- [x] Establish performance expectations
  - Purpose: Know system limits for batch processing
  - Steps:
    1. Use context7 MCP tool to review performance testing approaches
    2. Create `tests/performance/test_baseline_performance.py`:
       ```python
       import pytest
       import time
       from statistics import mean, stdev
       
       @pytest.mark.slow
       class TestBaselinePerformance:
           def test_single_file_performance(self, test_data_dir, neo4j_driver, temp_dir):
               """Establish single file processing baseline."""
               orchestrator = VTTKnowledgeExtractor(config={
                   "neo4j_driver": neo4j_driver,
                   "checkpoint_dir": temp_dir / "checkpoints"
               })
               
               vtt_file = test_data_dir / "standard.vtt"
               times = []
               
               for _ in range(5):
                   start = time.time()
                   orchestrator.process_vtt_files([vtt_file])
                   times.append(time.time() - start)
               
               avg_time = mean(times)
               assert avg_time < 5.0  # Should process in < 5 seconds
               
               # Save baseline
               with open(temp_dir / "performance_baseline.txt", "w") as f:
                   f.write(f"Average: {avg_time:.2f}s\n")
                   f.write(f"StdDev: {stdev(times):.2f}s\n")
       ```
    3. Add test for batch performance (files/second)
    4. Add test for memory usage growth
  - Validation: Performance baselines established

## Phase 5: Test Execution and CI Setup

### Task 5.1: Create Test Runner Script
- [x] Simplify test execution
  - Purpose: Easy way to run critical path tests
  - Steps:
    1. Use context7 MCP tool to review test automation patterns
    2. Create `scripts/run_critical_tests.py`:
       ```python
       #!/usr/bin/env python3
       """Run critical path tests."""
       import subprocess
       import sys
       
       def run_tests():
           """Run critical path tests with proper configuration."""
           # Ensure Docker is running
           try:
               subprocess.run(["docker", "ps"], check=True, capture_output=True)
           except subprocess.CalledProcessError:
               print("ERROR: Docker is not running!")
               return 1
           
           # Run tests
           cmd = [
               "pytest",
               "-v",
               "-m", "integration",
               "--tb=short",
               "tests/integration/test_neo4j_critical_path.py",
               "tests/integration/test_vtt_processing.py",
               "tests/integration/test_e2e_critical_path.py"
           ]
           
           result = subprocess.run(cmd)
           return result.returncode
       
       if __name__ == "__main__":
           sys.exit(run_tests())
       ```
    3. Make script executable: `chmod +x scripts/run_critical_tests.py`
    4. Add progress reporting
  - Validation: Script runs all critical tests

### Task 5.2: Setup GitHub Actions CI
- [x] Automate test execution
  - Purpose: Run tests on every commit
  - Steps:
    1. Use context7 MCP tool to review GitHub Actions for Python
    2. Create `.github/workflows/critical-tests.yml`:
       ```yaml
       name: Critical Path Tests
       
       on:
         push:
           branches: [main, develop]
         pull_request:
           branches: [main]
       
       jobs:
         test:
           runs-on: ubuntu-latest
           
           services:
             neo4j:
               image: neo4j:5.14.0
               env:
                 NEO4J_AUTH: neo4j/testpassword
               ports:
                 - 7687:7687
               options: >-
                 --health-cmd "neo4j status"
                 --health-interval 10s
                 --health-timeout 5s
                 --health-retries 5
           
           steps:
           - uses: actions/checkout@v3
           
           - name: Set up Python
             uses: actions/setup-python@v4
             with:
               python-version: '3.11'
           
           - name: Install dependencies
             run: |
               pip install -r requirements.txt
               pip install -r requirements-dev.txt
           
           - name: Run critical path tests
             env:
               NEO4J_URI: bolt://localhost:7687
               NEO4J_USER: neo4j
               NEO4J_PASSWORD: testpassword
             run: |
               pytest -v -m integration tests/integration/
       ```
    3. Add caching for dependencies
    4. Add test result reporting
  - Validation: CI runs on push to repository

### Task 5.3: Create Test Summary Report
- [x] Document test coverage and gaps
  - Purpose: Clear understanding of what's tested
  - Steps:
    1. Use context7 MCP tool to review test documentation practices
    2. Create `tests/CRITICAL_PATH_TESTS.md`:
       ```markdown
       # Critical Path Test Coverage
       
       ## What's Tested ✅
       - VTT file parsing (normal, corrupt, empty)
       - Neo4j storage operations
       - Knowledge extraction basic functionality
       - End-to-end pipeline flow
       - Batch processing with failures
       - Checkpoint recovery
       - Basic performance baselines
       
       ## What's NOT Tested ❌
       - Complex extraction scenarios
       - Large scale performance (1000+ files)
       - Concurrent processing
       - Advanced error recovery
       - Data quality validation
       
       ## Running Tests
       ```bash
       # Run all critical path tests
       ./scripts/run_critical_tests.py
       
       # Run specific test
       pytest tests/integration/test_neo4j_critical_path.py -v
       ```
       
       ## Known Limitations
       - Tests use simplified mocks for LLM
       - Performance tests use small files
       - No stress testing included
       ```
    3. Add troubleshooting section
    4. Add next steps for expanding tests
  - Validation: Documentation complete and accurate

## Success Criteria

1. **Import Errors**: < 10 import errors when running pytest
2. **Critical Path Coverage**: VTT → Knowledge Extraction → Neo4j fully tested
3. **Batch Processing**: Can process 10+ files with mixed success/failure
4. **Error Recovery**: System handles and reports failures gracefully
5. **Performance Baseline**: < 5 seconds per standard VTT file
6. **CI/CD**: Tests run automatically on every commit
7. **Documentation**: Clear guide for running and extending tests

## Technology Requirements

### Already Approved/Existing:
- Python 3.11 (existing)
- pytest (existing)
- Neo4j 5.14.0 (existing)
- Docker (required for test containers)

### New Technologies Requiring Approval:
- **testcontainers[neo4j]==3.7.1** - Provides Neo4j test containers
  - Purpose: Isolated Neo4j instances for testing
  - Alternative: Mock Neo4j entirely (not recommended)
  
- **pytest-timeout==2.2.0** - Timeout handling for tests
  - Purpose: Prevent hanging tests
  - Alternative: Manual timeout handling
  
- **pytest-xdist==3.5.0** - Parallel test execution
  - Purpose: Faster test runs
  - Alternative: Sequential execution (slower)

## Implementation Notes

1. **Start Simple**: Focus on happy path first, add edge cases later
2. **Use Real Components**: Avoid mocking where possible (except LLM)
3. **Fast Feedback**: Keep individual tests under 5 seconds
4. **Clear Failures**: Tests should clearly indicate what's broken
5. **Incremental Progress**: Each phase can be validated independently

This plan provides a pragmatic path to functional testing that supports your goal of processing hundreds of episodes reliably.