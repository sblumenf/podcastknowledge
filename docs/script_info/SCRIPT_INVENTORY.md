# Script Inventory

This document provides a comprehensive inventory of all scripts in the podcast knowledge project, organized by module and purpose.

## Root Directory Scripts

### Pipeline Orchestration
- `run_pipeline.sh` - Main pipeline runner that orchestrates transcriber and seeding modules
- `run_clustering.sh` - Run clustering process on existing data

### Podcast Management
- `add_podcast.sh` - Add a new podcast to the system
- `list_podcasts.sh` - List all configured podcasts
- `update_youtube_url.sh` - Update YouTube URLs for episodes
- `analyze_podcast_nodes.sh` - Analyze Neo4j node types for any podcast

## Seeding Pipeline Scripts

### Setup and Installation
Located in `seeding_pipeline/scripts/setup/`:
- `install.sh` - Install dependencies with virtual environment check
- `setup_venv.sh` - Create and configure virtual environment
- `validate_environment.py` - Validate environment setup

### Database Operations
Located in `seeding_pipeline/scripts/database/`:
- `clear_database.py` - Clear Neo4j database
- `inspect_db.py` - Inspect database contents
- `reset_database.py` - Reset database to clean state
- `check_database_contents.py` - Verify database integrity
- `comprehensive_database_check.py` - Full database validation
- `list_databases.py` - List available databases
- `cleanup_topics_from_database.py` - Remove topic nodes
- `delete_single_episode.py` - Delete specific episode
- `fix_database_duplicates.py` - Fix duplicate entries
- `recover_missing_embeddings.py` - Recover missing embeddings
- `recreate_indexes.py` - Recreate database indexes
- `show_index_queries.py` - Display index queries

### Analysis Tools
Located in `seeding_pipeline/scripts/analysis/`:
- `analyze_episode_segments.py` - Analyze episode segmentation
- `analyze_episode_units.py` - Analyze meaningful units
- `analyze_neo4j_nodes.py` - Analyze Neo4j node types and properties for any podcast
- `cluster_existing.py` - Run clustering on existing data
- `count_knowledge_units.py` - Count knowledge units
- `detect_semantic_gaps.py` - Detect semantic gaps between knowledge clusters
- `diagnose_meaningful_units.py` - Diagnose unit extraction
- `explore_cluster_connections.py` - Explore cluster relationships
- `find_313_segment_episode.py` - Find specific episode patterns
- `speaker_summary_report.py` - Generate speaker summaries
- `speaker_table_report.py` - Generate speaker tables
- Various episode-specific analysis scripts

### Testing Infrastructure
Located in `seeding_pipeline/scripts/testing/`:
- `run_tests.py` - Main test runner
- `run_minimal_tests.py` - Minimal test suite
- `run_critical_tests.py` - Critical path tests
- `run_smoke_tests.py` - Smoke tests
- `run_vtt_tests.py` - VTT-specific tests
- `run_coverage.sh` - Run tests with coverage
- Performance and integration test scripts

### Monitoring and Metrics
Located in `seeding_pipeline/scripts/monitoring/`:
- `metrics_dashboard.py` - Display metrics dashboard
- `monitor_caching.py` - Monitor cache performance
- `monitor_test_health.py` - Monitor test suite health
- `measure_performance.py` - Measure pipeline performance
- `benchmark_caching.py` - Benchmark caching system
- `verify_performance_optimizations.py` - Verify optimizations

### Maintenance and Fixes
Located in `seeding_pipeline/scripts/maintenance/`:
- `cleanup_imports.py` - Clean up import statements
- `cleanup_old_venvs.py` - Remove old virtual environments
- `fix_imports.py` - Fix import issues
- `fix_enum_values.py` - Fix enum value issues
- `manage_components.py` - Manage pipeline components
- `manage_failures.py` - Track and manage failures
- `manage_known_issues.py` - Track known issues
- `reset_to_virgin_state.py` - Reset system to initial state

### Validation
Located in `seeding_pipeline/scripts/validation/`:
- `pre_merge_validation.py` - Pre-merge checks
- `final_validation.py` - Final deployment validation
- `security_audit.py` - Security audit checks
- `validate_extraction.py` - Validate extraction quality
- `validate_providers.py` - Validate provider configurations

### Benchmarks
Located in `seeding_pipeline/scripts/benchmarks/`:
- `continuous_benchmark.py` - Continuous performance benchmarking
- `phase6_performance_benchmarks.py` - Specific performance benchmarks

## Transcriber Scripts

### Setup
Located in `transcriber/scripts/setup/`:
- `setup_test_env.sh` - Setup test environment

### Maintenance
Located in `transcriber/scripts/maintenance/`:
- `audit_imports.py` - Audit import statements
- `migrate_existing_transcriptions.py` - Migrate transcription data

### Utilities
Located in `transcriber/scripts/utilities/`:
- `check_transcribed.py` - Check transcription status
- `find_next_episodes.py` - Find episodes to transcribe

### Examples
Located in `transcriber/examples/`:
- `file_organizer_with_config.py` - File organization demo
- `youtube_search_demo.py` - YouTube API demo

## Shared Scripts

Located in `shared/scripts/`:
- `test_simple_tracking.sh` - Test tracking functionality
- `test_tracking_sync.sh` - Test cross-module synchronization
- `test_overlap_fix.py` - Test overlap detection

## Script Naming Conventions

- Setup/Install: `setup_*.sh`, `install_*.sh`
- Database operations: `db_*.py`, `*_database.py`
- Analysis tools: `analyze_*.py`, `diagnose_*.py`
- Test scripts: `test_*.py`, `run_*_tests.py`
- Validation: `validate_*.py`
- Monitoring: `monitor_*.py`, `measure_*.py`
- Maintenance: `fix_*.py`, `cleanup_*.py`
- Management: `manage_*.py`

## Best Practices

1. **Module Isolation**: Scripts should be placed in the module they primarily serve
2. **Cross-Module Scripts**: Only truly shared functionality goes in `shared/scripts/`
3. **Documentation**: Each script should have a docstring explaining its purpose
4. **Dependencies**: Scripts should check for required dependencies/environment
5. **Error Handling**: Scripts should provide clear error messages
6. **Naming**: Follow the established naming conventions for discoverability