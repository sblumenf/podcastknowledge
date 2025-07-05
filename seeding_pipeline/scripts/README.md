# Seeding Pipeline Scripts

This directory contains utility scripts for the seeding pipeline module, organized by purpose.

## Directory Structure

### setup/
Environment setup and installation scripts:
- `install.sh` - Install dependencies with venv check
- `setup_venv.sh` - Create and setup virtual environment
- `validate_environment.py` - Validate environment configuration

### database/
Database management and operations:
- `clear_database.py` - Clear Neo4j database
- `inspect_db.py` - Inspect database contents
- `reset_database.py` - Reset database to clean state
- `check_database_contents.py` - Check database content integrity
- `comprehensive_database_check.py` - Full database validation
- Database maintenance and recovery scripts

### analysis/
Data analysis and diagnostic tools:
- Episode analysis scripts
- Speaker analysis and reporting
- Meaningful unit diagnostics
- Relationship discovery tools
- Duplicate detection

### testing/
Test runners and test utilities:
- `run_tests.py` - Main test runner
- `run_minimal_tests.py` - Quick minimal test suite
- `run_critical_tests.py` - Critical path tests
- Performance and integration test scripts
- Test validation and verification tools

### monitoring/
Performance monitoring and metrics:
- `metrics_dashboard.py` - Metrics visualization
- Performance monitoring scripts
- Cache monitoring
- Benchmark utilities

### maintenance/
System maintenance and fixes:
- Import fixes and cleanup
- Component management
- Known issue tracking
- System reset utilities

### validation/
Deployment and system validation:
- Pre-merge validation
- Security audits
- Provider validation
- Extraction validation

### benchmarks/
Performance benchmarking tools:
- Continuous benchmarking
- Performance baseline tests

## Usage

Most scripts can be run directly from the seeding_pipeline directory:
```bash
python scripts/analysis/analyze_episode_segments.py
./scripts/setup/install.sh
```

For scripts requiring environment activation, ensure your virtual environment is active first.