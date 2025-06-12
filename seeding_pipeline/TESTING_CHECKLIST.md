# Testing Checklist

This checklist ensures that the VTT → Knowledge Graph pipeline is fully functional and ready for production use. Complete all items before considering the system "working".

**Last Updated**: 2025-05-31  
**Phase**: 5 - Test Execution & Monitoring  

## Environment Setup

### Python Environment
- [ ] Virtual environment activated (`source venv/bin/activate`)
- [ ] Python 3.9+ installed and accessible (`python --version`)
- [ ] All dependencies installed (`pip install -r requirements.txt`)
- [ ] Dev dependencies installed (`pip install -r requirements-dev.txt`)
- [ ] No import errors when running: `python -c "import pytest; import src"`

### Neo4j Database
- [ ] Neo4j Community Edition running (Docker or local install)
- [ ] Database accessible at configured URI (default: bolt://localhost:7687)
- [ ] Authentication working with configured credentials
- [ ] Can execute basic query: `MATCH (n) RETURN count(n)`
- [ ] Browser interface accessible at http://localhost:7474
- [ ] Test database cleanup working (can clear all nodes)

### Configuration
- [ ] `.env` file configured with correct Neo4j credentials
- [ ] Environment variables loaded correctly
- [ ] Configuration can be loaded: `python -c "from src.core.config import SeedingConfig; SeedingConfig()"`

## Core Functionality Testing

### VTT File Processing
- [ ] Can parse minimal VTT file (5 captions)
- [ ] Can parse standard VTT file (100 captions)
- [ ] Can parse complex VTT file (multi-speaker, overlapping)
- [ ] VTT parser handles timestamps correctly
- [ ] VTT parser extracts speaker information when present
- [ ] No errors with malformed VTT files (graceful failure)

### Knowledge Extraction
- [ ] Knowledge extracted and stored in Neo4j
- [ ] Podcast nodes created with correct metadata
- [ ] Episode nodes created and linked to podcasts
- [ ] Entities extracted from transcript text
- [ ] Relationships created between entities
- [ ] Extracted data is queryable in Neo4j browser

### Multi-File Processing
- [ ] Multiple episodes process correctly in sequence
- [ ] Episodes correctly linked to same podcast
- [ ] No data conflicts between different episodes
- [ ] Progress tracking works across multiple files
- [ ] Error in one file doesn't block others

### Data Integrity
- [ ] Can query extracted knowledge from Neo4j
- [ ] Node counts match expected values
- [ ] Relationship counts match expected values
- [ ] No duplicate nodes/relationships created
- [ ] Data persists between application restarts

## Test Suite Validation

### Test Infrastructure
- [ ] Can run unit tests: `./scripts/run_tests.py unit`
- [ ] Can run integration tests: `./scripts/run_tests.py integration`
- [ ] Can run E2E tests: `./scripts/run_tests.py e2e`
- [ ] Can run all tests: `./scripts/run_tests.py all`
- [ ] Test results saved to `test_results/` directory
- [ ] Can view test results: `./scripts/view_test_results.py`

### Critical Test Categories
- [ ] **Unit Tests**: Core components work in isolation
- [ ] **Integration Tests**: Components work together with services
- [ ] **E2E Tests**: Full pipeline VTT → Knowledge Graph works
- [ ] **Processing Tests**: VTT parsing and knowledge extraction work
- [ ] **API Tests**: REST endpoints function correctly

### Test Data Fixtures
- [ ] VTT sample files load correctly (`tests/fixtures/vtt_samples/`)
- [ ] Minimal.vtt fixture works (5 captions)
- [ ] Standard.vtt fixture works (100 captions) 
- [ ] Complex.vtt fixture works (multi-speaker)
- [ ] Test database cleanup between tests works
- [ ] No test data leakage between test runs

### E2E Test Scenarios
- [ ] **Basic Processing**: VTT file → parsed → extracted → stored
- [ ] **Knowledge Verification**: Correct entities and relationships created
- [ ] **Multi-Episode**: Multiple VTT files processed in sequence
- [ ] All E2E tests pass consistently
- [ ] E2E tests create expected data in Neo4j
- [ ] E2E tests clean up properly after execution

## CI/CD Pipeline

### GitHub Actions Workflow
- [ ] CI workflow file exists (`.github/workflows/ci.yml`)
- [ ] Workflow triggered on push to main/develop branches
- [ ] Workflow triggered on pull requests to main
- [ ] Neo4j service starts correctly in CI environment
- [ ] All dependencies install correctly in CI
- [ ] Tests run automatically in CI

### Test Result Reporting
- [ ] Test results visible in GitHub Actions tab
- [ ] Test failures block PR merges (branch protection enabled)
- [ ] Coverage reports generated and uploaded
- [ ] Test status badges work in README (if added)
- [ ] Failed tests show clear error messages
- [ ] CI passes consistently for known-good code

### Documentation
- [ ] CI/CD workflow documented (`docs/ci-workflow.md`)
- [ ] Troubleshooting guide available
- [ ] Developer workflow clearly explained
- [ ] Known issues documented if any exist

## Performance & Quality

### Basic Performance
- [ ] Single VTT file processes in reasonable time (< 30 seconds for 100 captions)
- [ ] Memory usage stays reasonable during processing
- [ ] No memory leaks during multiple file processing
- [ ] Database operations complete in reasonable time
- [ ] System handles expected workload without crashes

### Code Quality
- [ ] No critical security vulnerabilities
- [ ] Error handling works correctly (graceful failures)
- [ ] Logging provides useful debugging information
- [ ] Configuration is externalized (no hardcoded values)
- [ ] Code follows project conventions

## Production Readiness

### Error Handling
- [ ] Application handles Neo4j connection failures gracefully
- [ ] Application handles malformed VTT files gracefully
- [ ] Application handles disk space issues gracefully
- [ ] Application handles network timeouts gracefully
- [ ] Clear error messages for common failure scenarios

### Monitoring & Debugging
- [ ] Logging configured and working
- [ ] Can enable debug logging when needed
- [ ] Performance metrics available if needed
- [ ] Can diagnose common issues from logs
- [ ] Health check endpoints work (if applicable)

### Documentation
- [ ] README.md explains how to set up and run system
- [ ] Installation instructions are complete and accurate
- [ ] Troubleshooting guide covers common issues
- [ ] API documentation is current (if applicable)
- [ ] Architecture documentation explains key components

## Final Validation

### Complete Pipeline Test
- [ ] **End-to-End Manual Test**: Place VTT files in input directory
- [ ] **Execute**: Run full pipeline from start to finish
- [ ] **Verify**: Check Neo4j contains expected knowledge graph
- [ ] **Query**: Successfully extract insights from stored knowledge
- [ ] **Clean**: System can be reset and run again

### Deployment Readiness
- [ ] System works in clean environment (new machine/container)
- [ ] Installation process works from documentation alone
- [ ] All dependencies and requirements clearly specified
- [ ] Configuration is environment-agnostic
- [ ] System ready for hobby project deployment

---

## Checklist Completion

**Total Items**: 89  
**Completed**: ___  
**Success Criteria**: 85+ items completed (95%+ completion rate)

### Sign-off
- [ ] **Technical Validation**: All technical requirements met
- [ ] **Functional Validation**: Core functionality works end-to-end  
- [ ] **Quality Validation**: Tests pass, code quality acceptable
- [ ] **Documentation Validation**: Setup and usage clearly documented

**Validated by**: ________________  
**Date**: ________________  
**Notes**: ________________

---

## Usage Instructions

1. **Run through checklist systematically** - Don't skip items
2. **Document any failures** - Note what doesn't work and why
3. **Fix issues before proceeding** - Don't check items that don't work
4. **Retest after fixes** - Ensure fixes actually resolve issues
5. **Update documentation** - Keep checklist current as system evolves

This checklist should be run:
- Before any major release or deployment
- After significant code changes
- When setting up in new environments
- As part of troubleshooting process
- Quarterly for maintenance validation