# Scripts Directory

This directory contains utility scripts for managing and maintaining the podcast knowledge extraction pipeline.

## Embedding Recovery

### recover_missing_embeddings.py

Recovers missing embeddings for MeaningfulUnits that failed during pipeline processing.

#### When to Use

Run this script when:
- Pipeline logs show embedding generation failures
- You find `logs/embedding_failures/` contains failure JSON files
- Query `MATCH (m:MeaningfulUnit) WHERE m.embedding IS NULL RETURN count(m)` returns > 0
- After upgrading to Neo4j 5.11+ and creating vector indexes

#### Usage

```bash
# Preview what would be processed (recommended first step)
python scripts/recover_missing_embeddings.py --dry-run

# Process all units with missing embeddings (default batch size: 100)
python scripts/recover_missing_embeddings.py

# Process with custom batch size for rate limit management
python scripts/recover_missing_embeddings.py --batch-size 50

# Show help
python scripts/recover_missing_embeddings.py --help
```

#### Options

- `--dry-run`: Preview units that would be processed without making changes
- `--batch-size N`: Process N units at a time (default: 100)
  - Smaller batches reduce memory usage and API rate limit risk
  - Larger batches improve throughput

#### Output

The script provides progress updates and a final summary:
```
Recovery complete!
  Successfully recovered: 450
  Failed: 3
  Success rate: 99.3%
```

Failed embeddings are logged to `logs/embedding_recovery/recovery_failures_{timestamp}.json`

#### Performance Considerations

- Batch processing with configurable size
- 100ms delay between batches to respect API rate limits
- Efficient UNWIND operations for database updates
- Progress tracking for long-running recoveries

#### Error Handling

The script handles various failure scenarios:
- API rate limits: Logged, continues with next batch
- Database connection issues: Logged with full context
- Embedding service failures: Individual units tracked
- All failures saved to recovery log for analysis

## Database Management

### clear_database.py
Clears all data from the Neo4j database. Use with caution!

### reset_database.py
Resets the database schema and indexes.

### inspect_db.py
Provides database statistics and health information.

## Testing and Validation

### run_tests.py
Runs the complete test suite.

### validate_vtt_processing.py
Validates VTT file processing functionality.

### stress_test.py
Performs stress testing on the pipeline.

## Performance Monitoring

### measure_performance.py
Measures pipeline performance metrics.

### verify_performance_optimizations.py
Verifies that performance optimizations are working correctly.

### benchmark_caching.py
Tests caching performance.

## Speaker Analysis

### speaker_summary_report.py
Generates speaker identification summary reports.

### speaker_table_report.py
Creates detailed speaker distribution tables.

## Dependency Management

### analyze_dependencies.py
Analyzes project dependencies.

### fix_imports.py
Fixes import issues in the codebase.

## Environment Setup

### setup_venv.sh / setup_venv.bat
Sets up Python virtual environment.

### validate_environment.py
Validates that the environment is correctly configured.