# Migration Module

The migration module provides comprehensive tools for migrating from the monolithic podcast knowledge system to the modular architecture.

## Features

### 1. Schema Evolution Management
- Version tracking for database schema
- Forward and backward migrations
- Automatic rollback capabilities
- Schema validation

### 2. Data Migration
- Batch processing with progress tracking
- Checkpoint/resume functionality
- Data transformation and validation
- Relationship preservation

### 3. Compatibility Checking
- Pre-migration compatibility analysis
- Schema compatibility verification
- Data format validation
- Feature parity checking

### 4. Migration Validation
- Pre-migration validation
- Post-migration validation
- Data integrity checks
- Consistency verification

## Components

### SchemaManager
Manages database schema versions and migrations.

```python
from src.migration import SchemaManager
from src.providers.graph.neo4j import Neo4jProvider

# Initialize
graph_provider = Neo4jProvider(uri, username, password)
schema_manager = SchemaManager(graph_provider)

# Check current version
current = schema_manager.get_current_version()
print(f"Current version: {current.version}")

# Migrate to new version
success = schema_manager.migrate_to("1.1.0")

# Validate schema
validation = schema_manager.validate_schema()
```

### DataMigrator
Handles the actual data migration process.

```python
from src.migration import DataMigrator

# Initialize with checkpoint support
migrator = DataMigrator(
    graph_provider,
    checkpoint_dir=Path("migration_checkpoints"),
    batch_size=100
)

# Run migration (with dry-run option)
progress = migrator.migrate_all(dry_run=False)

# Check progress
for node_type, prog in progress.items():
    print(f"{node_type}: {prog.status.value}")
    print(f"  Processed: {prog.processed_items}/{prog.total_items}")
```

### CompatibilityChecker
Verifies compatibility between systems.

```python
from src.migration import CompatibilityChecker

# Initialize
checker = CompatibilityChecker(graph_provider)

# Run compatibility check
report = checker.check_all()

if report.compatible:
    print("Systems are compatible!")
else:
    print(f"Found {len(report.issues)} compatibility issues")
    
# Generate fix script
if not report.compatible:
    fix_script = checker.generate_compatibility_script(report)
```

### MigrationValidator
Validates data before and after migration.

```python
from src.migration import MigrationValidator

# Initialize
validator = MigrationValidator(graph_provider)

# Pre-migration validation
pre_result = validator.validate_pre_migration()
print(f"Pre-migration valid: {pre_result.valid}")

# Post-migration validation
post_result = validator.validate_post_migration()
print(f"Post-migration valid: {post_result.valid}")

# Compare before/after
comparison = validator.compare_before_after(
    pre_result.statistics,
    post_result.statistics
)
```

## CLI Usage

The migration module includes a comprehensive CLI for all migration tasks:

### Check Compatibility
```bash
python -m src.migration.cli check-compatibility
```

### Validate Before Migration
```bash
python -m src.migration.cli validate-pre
```

### Migrate Schema
```bash
# Dry run
python -m src.migration.cli migrate-schema --dry-run

# Actual migration
python -m src.migration.cli migrate-schema --target-version 1.1.0
```

### Migrate Data
```bash
# Dry run
python -m src.migration.cli migrate-data --dry-run

# Full migration with custom batch size
python -m src.migration.cli migrate-data --batch-size 500

# Resume from checkpoint
python -m src.migration.cli migrate-data --checkpoint-dir migration_checkpoints
```

### Validate After Migration
```bash
python -m src.migration.cli validate-post
```

### Rollback
```bash
python -m src.migration.cli rollback --target-date "2024-01-01 00:00:00"
```

## Migration Process

### Recommended Migration Steps

1. **Backup Database**
   ```bash
   neo4j-admin dump --database=neo4j --to=backup-$(date +%Y%m%d).dump
   ```

2. **Check Compatibility**
   ```bash
   python -m src.migration.cli check-compatibility
   ```
   
3. **Fix Compatibility Issues**
   - Review compatibility report
   - Apply generated fix script if needed
   - Re-run compatibility check

4. **Validate Pre-Migration State**
   ```bash
   python -m src.migration.cli validate-pre
   ```

5. **Run Schema Migration**
   ```bash
   python -m src.migration.cli migrate-schema --target-version 1.1.0
   ```

6. **Run Data Migration**
   ```bash
   # Dry run first
   python -m src.migration.cli migrate-data --dry-run
   
   # Actual migration
   python -m src.migration.cli migrate-data
   ```

7. **Validate Post-Migration**
   ```bash
   python -m src.migration.cli validate-post
   ```

8. **Test Application**
   - Run integration tests
   - Verify API functionality
   - Check data integrity

## Schema Versions

### Version 0.0.0 (Initial)
- Base schema from monolithic system
- No version tracking

### Version 1.0.0
- Added schema versioning
- Enhanced indexes for performance
- Added schema_version property to nodes

### Version 1.1.0
- Added migration history tracking
- Added backup markers
- Improved constraint management

## Troubleshooting

### Common Issues

1. **Duplicate IDs**
   - Use compatibility checker to identify
   - Apply fix script or manually resolve
   - Re-run validation

2. **Orphaned Nodes**
   - Check compatibility report
   - Decide whether to link or remove
   - Update relationships as needed

3. **Migration Failures**
   - Check logs for specific errors
   - Use checkpoints to resume
   - Consider smaller batch sizes

4. **Performance Issues**
   - Adjust batch_size parameter
   - Ensure adequate system resources
   - Consider off-peak migration

### Recovery Options

1. **Resume from Checkpoint**
   ```bash
   python -m src.migration.cli migrate-data
   ```

2. **Rollback Changes**
   ```bash
   python -m src.migration.cli rollback --target-date "2024-01-01 00:00:00"
   ```

3. **Restore from Backup**
   ```bash
   neo4j-admin load --from=backup-20240101.dump --database=neo4j
   ```

## Best Practices

1. **Always backup before migration**
2. **Run compatibility check first**
3. **Use dry-run mode for testing**
4. **Monitor system resources**
5. **Keep migration logs**
6. **Test thoroughly after migration**
7. **Have a rollback plan**

## Extending the Migration Module

### Adding New Schema Versions

Edit `schema_manager.py` and add to `MIGRATIONS`:

```python
SchemaVersion(
    version="1.2.0",
    description="Your description",
    migrations={
        "up": """
        // Your forward migration Cypher
        """,
        "down": """
        // Your rollback Cypher
        """
    }
)
```

### Custom Validators

Create custom validators by extending the validator:

```python
def validate_custom_rule(self, result: ValidationResult):
    """Custom validation logic."""
    # Your validation code
    pass
```

### Data Transformations

Add custom transformations in `data_migrator.py`:

```python
def _transform_custom_node(self, node: Dict[str, Any]) -> CustomModel:
    """Transform raw node data to custom model."""
    # Your transformation logic
    pass
```