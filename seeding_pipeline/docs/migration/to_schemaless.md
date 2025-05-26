# Migration Guide: Fixed Schema to Schemaless

This guide provides a comprehensive approach to migrating from the fixed schema knowledge graph to the flexible schemaless architecture.

## Table of Contents

1. [Pre-Migration Checklist](#pre-migration-checklist)
2. [Migration Strategies](#migration-strategies)
3. [Step-by-Step Migration Process](#step-by-step-migration-process)
4. [Data Backup Procedures](#data-backup-procedures)
5. [Rollback Instructions](#rollback-instructions)
6. [FAQ](#faq)
7. [Decision Tree](#decision-tree)

## Pre-Migration Checklist

Before beginning migration, ensure you have:

### Technical Requirements
- [ ] Neo4j version 5.x or higher
- [ ] Python 3.9+ with required dependencies
- [ ] At least 2x current database size in free disk space
- [ ] Backup storage location configured

### Access Requirements
- [ ] Neo4j admin credentials
- [ ] Read/write access to configuration files
- [ ] Access to monitoring dashboards
- [ ] Ability to schedule downtime (if needed)

### Preparation Steps
- [ ] Document current schema (entities, relationships, properties)
- [ ] Identify custom queries that need translation
- [ ] Review and update monitoring alerts
- [ ] Notify stakeholders of migration plan
- [ ] Run migration in test environment first

### Risk Assessment
- [ ] Identify critical queries and applications
- [ ] Document acceptable downtime window
- [ ] Prepare rollback plan
- [ ] Ensure team is trained on new schema

## Migration Strategies

### Strategy 1: Big Bang Migration
**Best for**: Small databases (<1M nodes), development environments

```bash
# Complete migration in one operation
python scripts/migrate_to_schemaless.py --action migrate --mode full
```

**Pros**: Simple, fast, clean break
**Cons**: Requires downtime, higher risk

### Strategy 2: Gradual Migration
**Best for**: Production systems, large databases

```bash
# Enable dual extraction mode
python scripts/migrate_to_schemaless.py --action configure --dual-mode

# Migrate incrementally
python scripts/migrate_to_schemaless.py --action migrate --mode incremental --batch-size 10000
```

**Pros**: No downtime, can rollback easily
**Cons**: Temporary performance impact, complex monitoring

### Strategy 3: Parallel Running
**Best for**: Mission-critical systems requiring validation

```yaml
# config/migration.yml
migration:
  strategy: parallel
  validation_period_days: 30
  comparison_metrics:
    - entity_count
    - relationship_coverage
    - query_performance
```

**Pros**: Full validation before cutover
**Cons**: Double resource usage, complex setup

## Step-by-Step Migration Process

### Phase 1: Preparation (Day 1-2)

#### 1.1 Backup Current Database
```bash
# Create full backup
neo4j-admin database dump neo4j --to-path=/backup/pre-migration

# Verify backup
neo4j-admin database check neo4j --from-path=/backup/pre-migration
```

#### 1.2 Document Current Schema
```cypher
// Export current schema
CALL apoc.meta.schema() YIELD value
RETURN value
```

#### 1.3 Set Up Test Environment
```bash
# Clone production data to test
neo4j-admin database copy neo4j test-db

# Start test instance
neo4j start --database=test-db
```

### Phase 2: Configuration (Day 3)

#### 2.1 Update Configuration Files
```yaml
# config/schemaless.yml
pipeline:
  use_schemaless_extraction: true
  schemaless_confidence_threshold: 0.7
  entity_resolution_threshold: 0.85
  
migration:
  dual_extraction_mode: true
  track_schema_changes: true
  enable_query_translation: true
```

#### 2.2 Enable Migration Mode
```python
# Update environment variables
export USE_SCHEMALESS_EXTRACTION=true
export MIGRATION_MODE=dual
export TRACK_SCHEMA_EVOLUTION=true
```

### Phase 3: Test Migration (Day 4-5)

#### 3.1 Run Test Migration
```bash
# Test on sample data
python scripts/migrate_to_schemaless.py \
  --action test \
  --sample-size 1000 \
  --compare-results
```

#### 3.2 Validate Results
```python
# Run validation script
python scripts/validate_migration.py \
  --check entities \
  --check relationships \
  --check properties \
  --generate-report
```

#### 3.3 Test Critical Queries
```cypher
// Original query
MATCH (p:Person)-[:SPEAKS_IN]->(s:Segment)
WHERE s.episode_id = $episodeId
RETURN p.name, count(s) as segments

// Translated query
MATCH (p {_type: 'Person'})-[r {_type: 'SPEAKS_IN'}]->(s {_type: 'Segment'})
WHERE s.episode_id = $episodeId
RETURN p.name, count(s) as segments
```

### Phase 4: Production Migration (Day 6-7)

#### 4.1 Enable Dual Mode
```bash
# Start dual extraction
python cli.py configure --dual-mode enable

# Monitor both schemas
python scripts/monitor_migration.py --mode dual
```

#### 4.2 Gradual Data Migration
```bash
# Migrate in batches
python scripts/migrate_to_schemaless.py \
  --action migrate \
  --mode incremental \
  --batch-size 50000 \
  --checkpoint-interval 10000
```

#### 4.3 Monitor Progress
```python
# Check migration status
python scripts/migrate_to_schemaless.py --action status

# Output:
# Migration Status:
# - Total Nodes: 1,000,000
# - Migrated: 750,000 (75%)
# - Remaining: 250,000
# - Estimated Time: 2 hours
# - Current Batch: 16/20
```

### Phase 5: Validation (Day 8-9)

#### 5.1 Compare Schemas
```cypher
// Count entities by type
MATCH (n)
WHERE exists(n._type)
RETURN n._type, count(n) as count
ORDER BY count DESC

// Compare with original
MATCH (n)
WHERE n:Person OR n:Organization OR n:Topic
RETURN labels(n)[0] as type, count(n) as count
```

#### 5.2 Performance Testing
```bash
# Run performance benchmarks
python scripts/benchmark_queries.py \
  --queries config/critical_queries.json \
  --compare fixed,schemaless
```

### Phase 6: Cutover (Day 10)

#### 6.1 Update Applications
```python
# Switch to schemaless mode
config.use_schemaless_extraction = True
config.dual_extraction_mode = False

# Update query translator
from src.migration.query_translator import QueryTranslator
translator = QueryTranslator(mode='schemaless')
```

#### 6.2 Disable Fixed Schema Processing
```bash
# Update configuration
python cli.py configure --extraction-mode schemaless

# Verify
python cli.py status --check extraction-mode
```

## Data Backup Procedures

### Full Backup
```bash
#!/bin/bash
# backup_neo4j.sh

BACKUP_DIR="/backup/neo4j/$(date +%Y%m%d_%H%M%S)"
mkdir -p $BACKUP_DIR

# Stop database for consistent backup
neo4j stop

# Dump database
neo4j-admin database dump neo4j --to-path=$BACKUP_DIR/neo4j.dump

# Backup configuration
cp -r /etc/neo4j $BACKUP_DIR/config
cp -r /var/lib/neo4j/conf $BACKUP_DIR/conf

# Start database
neo4j start

# Compress backup
tar -czf $BACKUP_DIR.tar.gz $BACKUP_DIR
rm -rf $BACKUP_DIR

echo "Backup completed: $BACKUP_DIR.tar.gz"
```

### Incremental Backup
```python
# Backup only changed nodes
def backup_incremental(since_timestamp):
    query = """
    MATCH (n)
    WHERE n.updated_at > $timestamp
    RETURN n
    """
    
    with driver.session() as session:
        results = session.run(query, timestamp=since_timestamp)
        
        with open(f'backup_incremental_{timestamp}.json', 'w') as f:
            for record in results:
                f.write(json.dumps(dict(record['n'])) + '\n')
```

## Rollback Instructions

### Immediate Rollback (Within 24 hours)
```bash
# 1. Stop current processing
python cli.py stop --force

# 2. Restore from backup
neo4j stop
neo4j-admin database restore neo4j --from-path=/backup/pre-migration/neo4j.dump
neo4j start

# 3. Revert configuration
git checkout HEAD~1 config/
export USE_SCHEMALESS_EXTRACTION=false

# 4. Restart services
python cli.py start
```

### Gradual Rollback (After extended use)
```python
# 1. Enable reverse migration mode
config.migration_direction = 'schemaless_to_fixed'

# 2. Run reverse migration
python scripts/migrate_to_fixed.py \
  --source schemaless \
  --target fixed \
  --validate
```

### Partial Rollback
```cypher
// Rollback specific entity types
MATCH (n {_type: 'Person'})
SET n:Person
REMOVE n._type

// Rollback relationships
MATCH ()-[r {_type: 'SPEAKS_IN'}]->()
SET r:SPEAKS_IN
REMOVE r._type
```

## FAQ

### Q: How long does migration take?
**A**: Depends on database size:
- <100K nodes: 1-2 hours
- 100K-1M nodes: 4-8 hours
- >1M nodes: 1-3 days

### Q: Can I migrate partially?
**A**: Yes, you can migrate:
- By entity type
- By date range
- By source (podcast)

### Q: What about existing queries?
**A**: Three options:
1. Use query translator (automatic)
2. Update queries manually
3. Use compatibility mode (both schemas)

### Q: Is downtime required?
**A**: Not with gradual migration or dual mode. Big bang requires 2-4 hours downtime.

### Q: How do I monitor migration?
**A**: Use provided monitoring tools:
```bash
# Real-time monitoring
python scripts/monitor_migration.py --dashboard

# Progress reports
python scripts/migrate_to_schemaless.py --action report
```

### Q: What if entity resolution fails?
**A**: Adjust threshold:
```python
config.entity_resolution_threshold = 0.9  # Stricter
# or
config.entity_resolution_threshold = 0.7  # More lenient
```

## Decision Tree

```
Start Migration?
│
├─ Database Size?
│  ├─ <100K nodes → Big Bang Migration
│  ├─ 100K-1M nodes → Gradual Migration
│  └─ >1M nodes → Parallel Running
│
├─ Downtime Tolerance?
│  ├─ Zero → Dual Mode + Gradual
│  ├─ <4 hours → Big Bang
│  └─ Flexible → Choose based on size
│
├─ Risk Tolerance?
│  ├─ Low → Parallel Running (30 days)
│  ├─ Medium → Dual Mode (7 days)
│  └─ High → Big Bang (1 day)
│
└─ Team Experience?
   ├─ New to Schemaless → Gradual + Training
   ├─ Some Experience → Dual Mode
   └─ Expert → Any Strategy
```

## Example Commands

### Complete Migration Workflow
```bash
# 1. Backup
./backup_neo4j.sh

# 2. Test
python scripts/migrate_to_schemaless.py --action test --sample-size 1000

# 3. Configure
export USE_SCHEMALESS_EXTRACTION=true
export MIGRATION_MODE=dual

# 4. Migrate
python scripts/migrate_to_schemaless.py --action migrate --mode gradual

# 5. Validate
python scripts/validate_migration.py --comprehensive

# 6. Cutover
python cli.py configure --extraction-mode schemaless

# 7. Monitor
python scripts/monitor_migration.py --post-migration
```

## Support

For migration support:
- Documentation: `/docs/migration/`
- Logs: `/var/log/migration/`
- Support: migration-support@example.com
- Emergency Rollback: 1-800-ROLLBACK