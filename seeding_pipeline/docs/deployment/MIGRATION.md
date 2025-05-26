# Neo4j Schema Migration Guide

## Migration Module

The modular system now includes a comprehensive migration module (`src/migration/`) that provides:

- **Schema Evolution Management**: Version tracking and migration execution
- **Data Migration**: Batch processing with checkpoint/resume support
- **Compatibility Checking**: Pre-migration analysis and validation
- **Migration Validation**: Data integrity and consistency checks

### Quick Start

1. **Check Compatibility**
   ```bash
   python -m src.migration.cli check-compatibility
   ```

2. **Validate Pre-Migration**
   ```bash
   python -m src.migration.cli validate-pre
   ```

3. **Migrate Schema**
   ```bash
   python -m src.migration.cli migrate-schema --target-version 1.1.0
   ```

4. **Migrate Data**
   ```bash
   python -m src.migration.cli migrate-data
   ```

5. **Validate Post-Migration**
   ```bash
   python -m src.migration.cli validate-post
   ```

For detailed documentation, see `src/migration/README.md`.

## Current Schema Documentation (v0.0.0)

### Node Types

1. **Podcast**
   - Properties: `id` (unique), `name`, `description`, `feed_url`, `website`, `hosts[]`, `categories[]`, `created_timestamp`, `updated_timestamp`
   - Constraints: `UNIQUE (id)`
   - Indexes: `name`

2. **Episode**
   - Properties: `id` (unique), `title`, `description`, `published_date`, `audio_url`, `duration`, `episode_number`, `season_number`, `processed_timestamp`, `sentiment_evolution[]`
   - Constraints: `UNIQUE (id)`
   - Indexes: `title`

3. **Segment**
   - Properties: `id` (unique), `text`, `start_time`, `end_time`, `speaker`, `sentiment`, `complexity_score`, `is_advertisement`, `embedding[]`
   - Constraints: `UNIQUE (id)`
   - Indexes: `text`

4. **Entity**
   - Properties: `id` (unique), `name`, `type`, `description`, `first_mentioned`, `mention_count`, `bridge_score`, `is_peripheral`, `embedding[]`
   - Constraints: `UNIQUE (id)`
   - Indexes: `name`, `bridge_score`, `is_peripheral`

5. **Insight**
   - Properties: `id` (unique), `insight_type`, `content`, `confidence_score`, `extracted_from_segment`, `is_bridge_insight`, `timestamp`
   - Constraints: `UNIQUE (id)`
   - Indexes: `insight_type`, `is_bridge_insight`

6. **Quote**
   - Properties: `id` (unique), `text`, `speaker`, `quote_type`, `context`, `timestamp`, `segment_id`
   - Constraints: `UNIQUE (id)`
   - Indexes: `quote_type`, `speaker`

7. **Topic**
   - Properties: `id` (unique), `name`, `description`, `trend`, `hierarchy_level`, `parent_topics[]`, `child_topics[]`
   - Constraints: `UNIQUE (id)`
   - Indexes: `name`, `trend`

8. **Speaker**
   - Properties: `id`, `name`, `role` (host/guest/recurring), `created_timestamp`
   - No explicit constraint in current schema

9. **PotentialConnection**
   - Properties: `id` (unique), `description`, `strength`, `entities[]`
   - Constraints: `UNIQUE (id)`

### Relationship Types

1. **Podcast Relationships**
   - `(:Podcast)-[:HAS_EPISODE]->(:Episode)`
   - `(:Podcast)-[:COVERS_TOPIC]->(:Topic)`

2. **Episode Relationships**
   - `(:Episode)-[:HAS_SEGMENT]->(:Segment)`
   - `(:Episode)-[:HAS_TOPIC]->(:Topic)`

3. **Entity Relationships**
   - `(:Entity)-[:MENTIONED_IN]->(:Episode)`
   - `(:Entity)-[:RELATED_TO]->(:Insight)`
   - `(:Entity)-[:CO_OCCURS_WITH]->(:Entity)` - weight property
   - `(:Entity)-[:CONTRIBUTES_TO]->(:Insight)`

4. **Speaker Relationships**
   - `(:Speaker)-[:SPEAKS_IN]->(:Episode)`
   - `(:Speaker)-[:SPEAKS]->(:Segment)`
   - `(:Speaker)-[:DISCUSSES]->(:Entity)` - count property

5. **Sentiment Relationships**
   - `(:Entity)-[:HAS_SENTIMENT]->(:Episode)` - score, polarity properties

6. **Quote Relationships**
   - `(:Quote)-[:EXTRACTED_FROM]->(:Segment)`
   - `(:Quote)-[:QUOTED_IN]->(:Episode)`

7. **Topic Relationships**
   - `(:Topic)-[:CONTAINS_TOPIC]->(:Topic)` - hierarchical
   - `(:Segment)-[:BELONGS_TO_TOPIC]->(:Topic)`

8. **Extraction Relationships**
   - `(:Insight)-[:EXTRACTED_FROM]->(:Episode)`

## Migration Strategy

### Schema Versioning System

```cypher
// Add schema version node
CREATE (v:SchemaVersion {
    version: "1.0.0",
    applied_at: datetime(),
    description: "Initial modular refactoring"
})
```

### Backward Compatibility

1. **Property Preservation**: All existing properties maintained
2. **ID Generation**: Keep same ID generation logic (MD5 hashing)
3. **Index Compatibility**: All indexes recreated with same names
4. **Relationship Types**: All relationship types preserved

### Migration Steps

#### Phase 1: Schema Validation (Non-Destructive)
```cypher
// Check current schema
CALL db.schema.visualization()

// Verify constraints exist
SHOW CONSTRAINTS

// Verify indexes exist  
SHOW INDEXES
```

#### Phase 2: Add Version Tracking
```cypher
// Add version to existing nodes
MATCH (n)
WHERE n:Podcast OR n:Episode OR n:Entity OR n:Insight OR n:Quote OR n:Topic
SET n.schema_version = "0.0.0"
```

#### Phase 3: Create Migration Checkpoint
```cypher
// Create backup marker
CREATE (b:BackupMarker {
    timestamp: datetime(),
    node_count: SIZE([(n) WHERE n:Podcast OR n:Episode | n]),
    relationship_count: SIZE([(r) | r])
})
```

### Data Validation Tool

Create `scripts/validate_migration.py` to compare:
1. Node counts by type
2. Property completeness
3. Relationship integrity
4. Embedding dimensions
5. ID uniqueness

### Rollback Strategy

1. **Pre-Migration Backup**: Neo4j dump before migration
2. **Version Tagging**: Tag nodes with schema version
3. **Gradual Migration**: Process podcasts in batches
4. **Validation Checkpoints**: Verify data integrity after each batch

## Breaking Changes

None - The modular system maintains full compatibility with existing schema.

## Future Schema Enhancements (v2.0.0)

Potential additions (not in current scope):
- Vector indexes for embeddings
- Full-text search indexes
- Additional metadata properties
- Time-series optimizations

## Schema Queries for Validation

```cypher
// Count nodes by type
MATCH (n)
RETURN labels(n)[0] as NodeType, count(n) as Count
ORDER BY Count DESC

// Verify required properties
MATCH (p:Podcast)
WHERE p.id IS NULL
RETURN count(p) as PodcastsWithoutId

// Check relationship integrity
MATCH (e:Episode)
WHERE NOT (e)<-[:HAS_EPISODE]-(:Podcast)
RETURN count(e) as OrphanedEpisodes
```