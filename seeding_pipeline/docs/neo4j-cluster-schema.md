# Neo4j Cluster Schema Design

## Overview

This document defines the complete Neo4j schema for the semantic clustering system that replaces topic extraction. All clustering data is stored in Neo4j as the single source of truth.

## Core Design Principles

1. **Neo4j as Single Source of Truth** - No external files (no JSON, NPY, CSV)
2. **Semantic Clustering** - Uses existing 768D MeaningfulUnit embeddings 
3. **Evolution Tracking** - Tracks how clusters split, merge, and evolve over time
4. **Independent Podcasts** - Each podcast has completely separate Neo4j database
5. **Automatic Clustering** - Runs automatically after episode processing

## Cluster Node Schema

### Cluster Node Properties

```cypher
CREATE (c:Cluster {
    id: STRING,                    // Format: "2024-W20_cluster_15"
    label: STRING,                 // Human-readable: "Electric Vehicles"  
    created_week: STRING,          // ISO week: "2024-W20"
    member_count: INTEGER,         // Number of MeaningfulUnits in cluster
    avg_confidence: FLOAT,         // Average HDBSCAN confidence score
    status: STRING,                // "active", "split", "merged"
    centroid: LIST<FLOAT>,         // 768D centroid vector stored as property
    min_cluster_size: INTEGER,     // HDBSCAN parameter used for this cluster
    epsilon: FLOAT,                // HDBSCAN epsilon parameter used
    created_timestamp: DATETIME    // When cluster was created
});
```

### Property Details

| Property | Type | Description | Example | Required |
|----------|------|-------------|---------|----------|
| `id` | STRING | Unique cluster identifier | `"2024-W20_cluster_15"` | ✓ |
| `label` | STRING | Human-readable cluster name from LLM | `"Electric Vehicles"` | ✓ |
| `created_week` | STRING | ISO week when cluster was created | `"2024-W20"` | ✓ |
| `member_count` | INTEGER | Number of MeaningfulUnits in cluster | `47` | ✓ |
| `avg_confidence` | FLOAT | Average HDBSCAN probability score | `0.87` | ✓ |
| `status` | STRING | Current cluster status | `"active"` | ✓ |
| `centroid` | LIST<FLOAT> | 768D centroid vector | `[0.123, -0.456, ...]` | ✓ |
| `min_cluster_size` | INTEGER | HDBSCAN parameter used | `5` | ✓ |
| `epsilon` | FLOAT | HDBSCAN epsilon parameter used | `0.3` | ✓ |
| `created_timestamp` | DATETIME | Creation timestamp | `datetime()` | ✓ |

### Status Values

- **`active`** - Currently active cluster with new assignments
- **`split`** - Cluster that has split into multiple clusters  
- **`merged`** - Cluster that has been merged into another cluster

### ID Format Convention

Cluster IDs follow the format: `{WEEK}_{TYPE}_{NUMBER}`

Examples:
- `2024-W20_cluster_15` - Normal cluster
- `2024-W21_cluster_03` - Normal cluster

This format ensures:
- **Temporal ordering** - Week prefix for chronological sorting
- **Type identification** - Clear cluster type designation  
- **Uniqueness** - Sequential numbering within each week
- **Traceability** - Easy to identify when cluster was created

## Constraints and Indexes

### Constraints

```cypher
// Ensure cluster ID uniqueness
CREATE CONSTRAINT cluster_id_unique FOR (c:Cluster) REQUIRE c.id IS UNIQUE;

// Ensure label exists
CREATE CONSTRAINT cluster_label_required FOR (c:Cluster) REQUIRE c.label IS NOT NULL;

// Ensure status is valid
CREATE CONSTRAINT cluster_status_valid FOR (c:Cluster) 
REQUIRE c.status IN ['active', 'split', 'merged'];
```

### Indexes for Performance

```cypher
// Index for cluster labels (visualization queries)
CREATE INDEX cluster_label_idx FOR (c:Cluster) ON (c.label);

// Index for week-based queries (evolution tracking)
CREATE INDEX cluster_week_idx FOR (c:Cluster) ON (c.created_week);

// Index for status filtering (active clusters)
CREATE INDEX cluster_status_idx FOR (c:Cluster) ON (c.status);

// Composite index for active clusters by week
CREATE INDEX cluster_active_week_idx FOR (c:Cluster) ON (c.status, c.created_week);
```

## Example Cluster Nodes

### Electric Vehicles Cluster
```cypher
CREATE (c1:Cluster {
    id: "2024-W20_cluster_15",
    label: "Electric Vehicles",
    created_week: "2024-W20", 
    member_count: 47,
    avg_confidence: 0.87,
    status: "active",
    centroid: [0.123, -0.456, 0.789, ...], // 768 dimensions
    min_cluster_size: 5,
    epsilon: 0.3,
    created_timestamp: datetime()
});
```

### AI & Machine Learning Cluster  
```cypher
CREATE (c2:Cluster {
    id: "2024-W20_cluster_08",
    label: "AI & Machine Learning", 
    created_week: "2024-W20",
    member_count: 63,
    avg_confidence: 0.92,
    status: "active", 
    centroid: [0.234, 0.567, -0.123, ...], // 768 dimensions
    min_cluster_size: 5,
    epsilon: 0.3,
    created_timestamp: datetime()
});
```

### Split Cluster Example
```cypher
CREATE (c3:Cluster {
    id: "2024-W15_cluster_12",
    label: "Transportation",
    created_week: "2024-W15",
    member_count: 89,
    avg_confidence: 0.78,
    status: "split", // This cluster split into multiple clusters
    centroid: [0.345, 0.678, -0.234, ...], 
    min_cluster_size: 8,
    epsilon: 0.25,
    created_timestamp: datetime()
});
```

## Storage Considerations

### Centroid Storage
- **Location**: Stored directly as Neo4j node property
- **Format**: LIST<FLOAT> with 768 dimensions
- **Rationale**: Keeps all data in Neo4j, no external files needed
- **Performance**: Neo4j handles large property lists efficiently

### Memory Usage
- 768 floats × 4 bytes = ~3KB per centroid
- 1000 clusters = ~3MB total centroid storage
- Negligible impact on Neo4j performance

### Backup Considerations
- All cluster data included in standard Neo4j backups
- No separate backup strategy needed for external files
- Complete cluster state recoverable from database alone

## Query Patterns

### Get All Active Clusters
```cypher
MATCH (c:Cluster {status: 'active'})
RETURN c.id, c.label, c.member_count, c.created_week
ORDER BY c.member_count DESC;
```

### Find Clusters by Week Range
```cypher
MATCH (c:Cluster)
WHERE c.created_week >= '2024-W15' AND c.created_week <= '2024-W20'
RETURN c.id, c.label, c.status, c.created_week
ORDER BY c.created_week, c.id;
```

### Get Cluster with Details
```cypher
MATCH (c:Cluster {id: $cluster_id})
RETURN c.id, c.label, c.member_count, c.avg_confidence, 
       c.status, c.created_week, c.centroid;
```

## Schema Validation

### Validation Queries

```cypher
// Check all clusters have required properties
MATCH (c:Cluster)
WHERE c.id IS NULL OR c.label IS NULL OR c.status IS NULL
RETURN count(c) as invalid_clusters;

// Check status values are valid  
MATCH (c:Cluster)
WHERE NOT c.status IN ['active', 'split', 'merged']
RETURN c.id, c.status;

// Check centroid dimensions
MATCH (c:Cluster)
WHERE size(c.centroid) <> 768
RETURN c.id, size(c.centroid) as centroid_size;
```

### Health Check Query
```cypher
MATCH (c:Cluster)
RETURN c.status, count(c) as count
ORDER BY c.status;
```

Expected output:
```
╭──────────┬───────╮
│ status   │ count │
├──────────┼───────┤
│ active   │   45  │
│ merged   │    8  │  
│ split    │    3  │
╰──────────┴───────╯
```

## MeaningfulUnit to Cluster Relationships

### IN_CLUSTER Relationship Schema

The `IN_CLUSTER` relationship connects MeaningfulUnits to their assigned Clusters, replacing the episode-level topic assignments.

```cypher
CREATE (m:MeaningfulUnit)-[:IN_CLUSTER {
    confidence: FLOAT,             // HDBSCAN probability score (0.0-1.0)
    assigned_week: STRING,         // Week when assignment was made: "2024-W20"  
    is_primary: BOOLEAN,           // True for current assignment, false for archived
    cluster_distance: FLOAT,       // Distance from unit embedding to cluster centroid
    assignment_method: STRING      // "hdbscan" or "manual" for future curation
}]->(c:Cluster);
```

### Relationship Properties

| Property | Type | Description | Example | Required |
|----------|------|-------------|---------|----------|
| `confidence` | FLOAT | HDBSCAN probability score | `0.92` | ✓ |
| `assigned_week` | STRING | ISO week of assignment | `"2024-W20"` | ✓ |
| `is_primary` | BOOLEAN | Current vs archived assignment | `true` | ✓ |
| `cluster_distance` | FLOAT | Distance to cluster centroid | `0.23` | ✓ |
| `assignment_method` | STRING | How assignment was made | `"hdbscan"` | ✓ |

### Assignment Method Values

- **`hdbscan`** - Automatic assignment via HDBSCAN clustering
- **`manual`** - Manual assignment for future curation capabilities
- **`inherited`** - Assignment inherited from cluster split/merge

### Confidence Score Interpretation

- **0.9-1.0** - Very confident assignment
- **0.7-0.9** - Confident assignment  
- **0.5-0.7** - Moderate confidence
- **0.0-0.5** - Low confidence (review recommended)

### Assignment Lifecycle

1. **New Assignment**: `is_primary=true` for current cluster assignment
2. **Cluster Evolution**: Previous assignments marked `is_primary=false` (archived)
3. **New Clustering Run**: New relationships created with `is_primary=true`

### Example Relationships

```cypher
// High confidence assignment
CREATE (m1:MeaningfulUnit {id: "ep1_unit_05"})-[:IN_CLUSTER {
    confidence: 0.94,
    assigned_week: "2024-W20",
    is_primary: true,
    cluster_distance: 0.12,
    assignment_method: "hdbscan"
}]->(c1:Cluster {id: "2024-W20_cluster_15"});

// Moderate confidence assignment  
CREATE (m2:MeaningfulUnit {id: "ep2_unit_12"})-[:IN_CLUSTER {
    confidence: 0.67,
    assigned_week: "2024-W20", 
    is_primary: true,
    cluster_distance: 0.31,
    assignment_method: "hdbscan"
}]->(c1:Cluster {id: "2024-W20_cluster_15"});

// Archived assignment from previous week
CREATE (m1:MeaningfulUnit {id: "ep1_unit_05"})-[:IN_CLUSTER {
    confidence: 0.88,
    assigned_week: "2024-W19",
    is_primary: false,  // Archived
    cluster_distance: 0.18,
    assignment_method: "hdbscan"  
}]->(c_old:Cluster {id: "2024-W19_cluster_08"});
```

### Indexes for IN_CLUSTER Relationships

```cypher
// Index for finding current assignments
CREATE INDEX in_cluster_primary_idx FOR ()-[r:IN_CLUSTER]-() ON (r.is_primary);

// Index for week-based queries
CREATE INDEX in_cluster_week_idx FOR ()-[r:IN_CLUSTER]-() ON (r.assigned_week);

// Composite index for current assignments by week
CREATE INDEX in_cluster_primary_week_idx FOR ()-[r:IN_CLUSTER]-() ON (r.is_primary, r.assigned_week);

// Index for confidence-based filtering
CREATE INDEX in_cluster_confidence_idx FOR ()-[r:IN_CLUSTER]-() ON (r.confidence);
```

### Query Patterns for IN_CLUSTER

#### Get All Units in a Cluster
```cypher
MATCH (c:Cluster {id: $cluster_id})<-[r:IN_CLUSTER {is_primary: true}]-(m:MeaningfulUnit)
RETURN m.id, m.summary, r.confidence, r.cluster_distance
ORDER BY r.confidence DESC;
```

#### Find High-Confidence Assignments
```cypher
MATCH (m:MeaningfulUnit)-[r:IN_CLUSTER {is_primary: true}]->(c:Cluster)
WHERE r.confidence >= 0.8
RETURN c.label, count(m) as high_confidence_units, avg(r.confidence) as avg_confidence
ORDER BY high_confidence_units DESC;
```

#### Get Current Cluster for a MeaningfulUnit
```cypher
MATCH (m:MeaningfulUnit {id: $unit_id})-[r:IN_CLUSTER {is_primary: true}]->(c:Cluster)
RETURN c.id, c.label, r.confidence, r.assigned_week;
```

#### Find Low-Confidence Assignments (for review)
```cypher
MATCH (m:MeaningfulUnit)-[r:IN_CLUSTER {is_primary: true}]->(c:Cluster)
WHERE r.confidence < 0.6
RETURN m.id, m.summary, c.label, r.confidence
ORDER BY r.confidence ASC
LIMIT 20;
```

#### Track Assignment History for a Unit
```cypher
MATCH (m:MeaningfulUnit {id: $unit_id})-[r:IN_CLUSTER]->(c:Cluster)
RETURN c.label, r.assigned_week, r.confidence, r.is_primary
ORDER BY r.assigned_week DESC;
```

### Archive Management

When clusters evolve (split/merge), previous assignments are archived but not deleted:

```cypher
// Archive previous assignments before creating new ones
MATCH (m:MeaningfulUnit)-[r:IN_CLUSTER {is_primary: true}]->(c:Cluster)
SET r.is_primary = false, r.archived_week = $current_week
RETURN count(r) as archived_assignments;
```

### Validation Queries

```cypher
// Check for units with multiple primary assignments (should be 0)
MATCH (m:MeaningfulUnit)-[r:IN_CLUSTER {is_primary: true}]->()
WITH m, count(r) as assignment_count
WHERE assignment_count > 1
RETURN m.id, assignment_count;

// Check confidence score ranges
MATCH ()-[r:IN_CLUSTER {is_primary: true}]->()
WHERE r.confidence < 0 OR r.confidence > 1
RETURN count(r) as invalid_confidence_scores;

// Get assignment statistics
MATCH ()-[r:IN_CLUSTER {is_primary: true}]->()
RETURN 
    count(r) as total_assignments,
    avg(r.confidence) as avg_confidence,
    min(r.confidence) as min_confidence,
    max(r.confidence) as max_confidence;
```

## ClusteringState Tracking Nodes

### ClusteringState Node Schema

The `ClusteringState` node tracks metadata about each clustering run, enabling evolution tracking and system monitoring.

```cypher
CREATE (cs:ClusteringState {
    id: STRING,                    // Format: "state_2024-W20_20241201_143022"
    week: STRING,                  // ISO week: "2024-W20"
    timestamp: DATETIME,           // When clustering was executed
    n_clusters: INTEGER,           // Number of clusters created
    n_outliers: INTEGER,           // Number of outlier MeaningfulUnits
    total_units: INTEGER,          // Total MeaningfulUnits processed
    outlier_ratio: FLOAT,          // Percentage of outliers (0.0-1.0)
    avg_cluster_size: FLOAT,       // Average units per cluster
    min_cluster_size: INTEGER,     // HDBSCAN parameter used
    epsilon: FLOAT,                // HDBSCAN epsilon parameter used
    execution_time_seconds: FLOAT, // How long clustering took
    quality_score: FLOAT,          // Overall quality metric (0.0-1.0)
    status: STRING,                // "completed", "failed", "in_progress"
    error_message: STRING,         // Error details if status="failed"
    config_hash: STRING            // Hash of clustering config used
});
```

### ClusteringState Properties

| Property | Type | Description | Example | Required |
|----------|------|-------------|---------|----------|
| `id` | STRING | Unique state identifier | `"state_2024-W20_20241201_143022"` | ✓ |
| `week` | STRING | ISO week of clustering run | `"2024-W20"` | ✓ |
| `timestamp` | DATETIME | Exact execution time | `datetime()` | ✓ |
| `n_clusters` | INTEGER | Clusters created | `23` | ✓ |
| `n_outliers` | INTEGER | Outlier units | `45` | ✓ |
| `total_units` | INTEGER | Total units processed | `1247` | ✓ |
| `outlier_ratio` | FLOAT | Outlier percentage | `0.036` | ✓ |
| `avg_cluster_size` | FLOAT | Average cluster size | `52.5` | ✓ |
| `min_cluster_size` | INTEGER | HDBSCAN parameter | `5` | ✓ |
| `epsilon` | FLOAT | HDBSCAN epsilon | `0.3` | ✓ |
| `execution_time_seconds` | FLOAT | Runtime duration | `24.7` | ✓ |
| `quality_score` | FLOAT | Quality assessment | `0.85` | ✓ |
| `status` | STRING | Execution status | `"completed"` | ✓ |
| `error_message` | STRING | Error details | `null` | ◯ |
| `config_hash` | STRING | Config fingerprint | `"md5:abc123..."` | ✓ |

### Status Values

- **`completed`** - Clustering completed successfully
- **`failed`** - Clustering failed with errors
- **`in_progress`** - Currently executing (for long-running jobs)

### ID Format Convention

ClusteringState IDs follow: `state_{WEEK}_{YYYYMMDD}_{HHMMSS}`

Examples:
- `state_2024-W20_20241201_143022` - Completed clustering run
- `state_2024-W21_20241208_091545` - Another completed run

### Quality Score Calculation

Quality score (0.0-1.0) combines multiple factors:

```python
def calculate_quality_score(clustering_results):
    """Calculate overall clustering quality score."""
    
    # Factor 1: Outlier ratio (lower is better)
    outlier_penalty = min(clustering_results['outlier_ratio'] * 2, 1.0)
    
    # Factor 2: Cluster size distribution (balanced is better)
    cluster_sizes = [len(units) for units in clustering_results['clusters'].values()]
    size_variance = np.var(cluster_sizes) / np.mean(cluster_sizes) if cluster_sizes else 1.0
    size_score = max(0, 1 - (size_variance / 10))  # Normalize variance penalty
    
    # Factor 3: Number of clusters (reasonable range is better)
    total_units = clustering_results['total_units']
    expected_clusters = max(5, int(np.sqrt(total_units) / 3))
    actual_clusters = clustering_results['n_clusters']
    cluster_ratio = min(actual_clusters, expected_clusters) / max(actual_clusters, expected_clusters)
    
    # Combine factors
    quality_score = (
        (1 - outlier_penalty) * 0.4 +    # 40% weight on outlier ratio
        size_score * 0.3 +               # 30% weight on size distribution  
        cluster_ratio * 0.3              # 30% weight on cluster count
    )
    
    return round(quality_score, 3)
```

### Example ClusteringState Nodes

#### Successful Clustering Run
```cypher
CREATE (cs1:ClusteringState {
    id: "state_2024-W20_20241201_143022",
    week: "2024-W20",
    timestamp: datetime("2024-12-01T14:30:22Z"),
    n_clusters: 23,
    n_outliers: 45,
    total_units: 1247,
    outlier_ratio: 0.036,
    avg_cluster_size: 52.3,
    min_cluster_size: 5,
    epsilon: 0.3,
    execution_time_seconds: 24.7,
    quality_score: 0.85,
    status: "completed",
    error_message: null,
    config_hash: "md5:abc123def456"
});
```

#### Failed Clustering Run
```cypher
CREATE (cs2:ClusteringState {
    id: "state_2024-W20_20241201_152012", 
    week: "2024-W20",
    timestamp: datetime("2024-12-01T15:20:12Z"),
    n_clusters: 0,
    n_outliers: 0,
    total_units: 1247,
    outlier_ratio: 0.0,
    avg_cluster_size: 0.0,
    min_cluster_size: 5,
    epsilon: 0.3,
    execution_time_seconds: 2.1,
    quality_score: 0.0,
    status: "failed",
    error_message: "HDBSCAN failed: insufficient memory",
    config_hash: "md5:abc123def456"
});
```

### ClusteringState Relationships

#### HAS_STATE Relationship (to Clusters)

Links clustering runs to the clusters they created:

```cypher
CREATE (cs:ClusteringState)-[:HAS_STATE {
    creation_order: INTEGER         // Order clusters were created (1, 2, 3...)
}]->(c:Cluster);
```

#### PRECEDED_BY Relationship (between ClusteringStates)

Links clustering runs in temporal sequence:

```cypher
CREATE (cs_current:ClusteringState)-[:PRECEDED_BY {
    weeks_gap: INTEGER,             // Number of weeks between runs
    config_changed: BOOLEAN         // Whether clustering config changed
}]->(cs_previous:ClusteringState);
```

### Indexes for ClusteringState

```cypher
// Primary constraint
CREATE CONSTRAINT clustering_state_id_unique FOR (cs:ClusteringState) REQUIRE cs.id IS UNIQUE;

// Index for week-based queries
CREATE INDEX clustering_state_week_idx FOR (cs:ClusteringState) ON (cs.week);

// Index for status filtering
CREATE INDEX clustering_state_status_idx FOR (cs:ClusteringState) ON (cs.status);

// Index for timestamp ordering
CREATE INDEX clustering_state_timestamp_idx FOR (cs:ClusteringState) ON (cs.timestamp);

// Composite index for completed runs by week
CREATE INDEX clustering_state_completed_week_idx FOR (cs:ClusteringState) ON (cs.status, cs.week);
```

### Query Patterns for ClusteringState

#### Get Latest Clustering Run
```cypher
MATCH (cs:ClusteringState {status: "completed"})
RETURN cs.id, cs.week, cs.timestamp, cs.n_clusters, cs.quality_score
ORDER BY cs.timestamp DESC
LIMIT 1;
```

#### Get Clustering History for Monitoring
```cypher
MATCH (cs:ClusteringState)
WHERE cs.timestamp >= datetime() - duration({days: 30})
RETURN cs.week, cs.timestamp, cs.n_clusters, cs.outlier_ratio, 
       cs.quality_score, cs.execution_time_seconds, cs.status
ORDER BY cs.timestamp DESC;
```

#### Find Quality Issues
```cypher
MATCH (cs:ClusteringState {status: "completed"})
WHERE cs.quality_score < 0.7 OR cs.outlier_ratio > 0.2
RETURN cs.week, cs.quality_score, cs.outlier_ratio, cs.n_clusters
ORDER BY cs.quality_score ASC;
```

#### Get Config Changes Over Time
```cypher
MATCH (cs:ClusteringState {status: "completed"})
RETURN cs.week, cs.min_cluster_size, cs.epsilon, cs.config_hash
ORDER BY cs.timestamp;
```

#### Evolution Tracking Query
```cypher
MATCH (cs_current:ClusteringState)-[:PRECEDED_BY]->(cs_previous:ClusteringState)
WHERE cs_current.status = "completed" AND cs_previous.status = "completed"
RETURN 
    cs_previous.week as prev_week,
    cs_current.week as current_week,
    cs_previous.n_clusters as prev_clusters,
    cs_current.n_clusters as current_clusters,
    cs_current.n_clusters - cs_previous.n_clusters as cluster_change
ORDER BY cs_current.timestamp DESC
LIMIT 10;
```

### Monitoring and Alerting Queries

#### System Health Check
```cypher
MATCH (cs:ClusteringState)
WHERE cs.timestamp >= datetime() - duration({days: 7})
WITH cs.status, count(cs) as count
RETURN cs.status, count
ORDER BY cs.status;
```

#### Performance Trending
```cypher
MATCH (cs:ClusteringState {status: "completed"})
WHERE cs.timestamp >= datetime() - duration({days: 90})
RETURN 
    cs.week,
    cs.execution_time_seconds,
    cs.total_units,
    cs.execution_time_seconds / cs.total_units as seconds_per_unit
ORDER BY cs.timestamp;
```

#### Quality Trending
```cypher
MATCH (cs:ClusteringState {status: "completed"})
WHERE cs.timestamp >= datetime() - duration({days: 90})
RETURN 
    cs.week,
    cs.quality_score,
    cs.outlier_ratio,
    cs.n_clusters
ORDER BY cs.timestamp;
```

### Cleanup and Maintenance

#### Archive Old ClusteringState Records
```cypher
// Keep last 52 weeks (1 year) of successful runs
MATCH (cs:ClusteringState {status: "completed"})
WHERE cs.timestamp < datetime() - duration({weeks: 52})
WITH cs
ORDER BY cs.timestamp
SKIP 52  // Keep at least 52 most recent
DETACH DELETE cs;
```

#### Clean Failed Runs Older Than 30 Days
```cypher
MATCH (cs:ClusteringState {status: "failed"})
WHERE cs.timestamp < datetime() - duration({days: 30})
DETACH DELETE cs;
```

## Evolution Tracking Relationships

### EVOLVED_INTO Relationship Schema

The `EVOLVED_INTO` relationship tracks how clusters change over time, supporting split, merge, and continuation detection.

```cypher
CREATE (c_old:Cluster)-[:EVOLVED_INTO {
    evolution_type: STRING,        // "split", "merge", "continuation"
    evolution_week: STRING,        // Week when evolution occurred: "2024-W21"
    proportion: FLOAT,             // Proportion of units transferred (0.0-1.0)
    confidence: FLOAT,             // Confidence in evolution detection (0.0-1.0)
    unit_count: INTEGER,           // Number of units involved in evolution
    similarity_score: FLOAT,       // Centroid similarity before/after (0.0-1.0)
    evolution_reason: STRING       // "natural_drift", "parameter_change", "new_content"
}]->(c_new:Cluster);
```

### Evolution Relationship Properties

| Property | Type | Description | Example | Required |
|----------|------|-------------|---------|----------|
| `evolution_type` | STRING | Type of evolution | `"split"` | ✓ |
| `evolution_week` | STRING | Week evolution occurred | `"2024-W21"` | ✓ |
| `proportion` | FLOAT | Units transferred ratio | `0.65` | ✓ |
| `confidence` | FLOAT | Detection confidence | `0.87` | ✓ |
| `unit_count` | INTEGER | Units involved | `42` | ✓ |
| `similarity_score` | FLOAT | Centroid similarity | `0.73` | ✓ |
| `evolution_reason` | STRING | Why evolution occurred | `"natural_drift"` | ✓ |

### Evolution Types

#### Split Evolution
One cluster becomes multiple clusters:
```cypher
// Transportation cluster splits into Electric Cars and Gas Cars
CREATE (c_transport:Cluster {id: "2024-W20_cluster_05", label: "Transportation"})
      -[:EVOLVED_INTO {
          evolution_type: "split",
          evolution_week: "2024-W21", 
          proportion: 0.65,           // 65% of units went to Electric Cars
          confidence: 0.89,
          unit_count: 42,
          similarity_score: 0.72,
          evolution_reason: "natural_drift"
      }]->(c_electric:Cluster {id: "2024-W21_cluster_08", label: "Electric Cars"});

CREATE (c_transport)-[:EVOLVED_INTO {
          evolution_type: "split",
          evolution_week: "2024-W21",
          proportion: 0.35,           // 35% of units went to Gas Cars  
          confidence: 0.89,
          unit_count: 23,
          similarity_score: 0.68,
          evolution_reason: "natural_drift"
      }]->(c_gas:Cluster {id: "2024-W21_cluster_12", label: "Gas Cars"});
```

#### Merge Evolution  
Multiple clusters become one cluster:
```cypher
// Tesla and Rivian clusters merge into Electric Vehicles
CREATE (c_tesla:Cluster {id: "2024-W20_cluster_03", label: "Tesla"})
      -[:EVOLVED_INTO {
          evolution_type: "merge", 
          evolution_week: "2024-W21",
          proportion: 0.7,            // Tesla contributed 70% to merged cluster
          confidence: 0.92,
          unit_count: 35,
          similarity_score: 0.84,
          evolution_reason: "natural_drift"
      }]->(c_ev:Cluster {id: "2024-W21_cluster_15", label: "Electric Vehicles"});

CREATE (c_rivian:Cluster {id: "2024-W20_cluster_07", label: "Rivian"})
      -[:EVOLVED_INTO {
          evolution_type: "merge",
          evolution_week: "2024-W21", 
          proportion: 0.3,            // Rivian contributed 30% to merged cluster
          confidence: 0.92,
          unit_count: 15,
          similarity_score: 0.79,
          evolution_reason: "natural_drift"
      }]->(c_ev);
```

#### Continuation Evolution
Cluster continues with minimal changes:
```cypher
// AI & Machine Learning cluster continues mostly unchanged
CREATE (c_ai_old:Cluster {id: "2024-W20_cluster_02", label: "AI & Machine Learning"})
      -[:EVOLVED_INTO {
          evolution_type: "continuation",
          evolution_week: "2024-W21",
          proportion: 0.93,           // 93% of units stayed in cluster
          confidence: 0.95,
          unit_count: 58,
          similarity_score: 0.96,
          evolution_reason: "natural_drift"
      }]->(c_ai_new:Cluster {id: "2024-W21_cluster_02", label: "AI & Machine Learning"});
```

### Evolution Reason Values

- **`natural_drift`** - Organic topic evolution over time
- **`parameter_change`** - HDBSCAN parameters changed
- **`new_content`** - Significant new content added
- **`external_event`** - Response to real-world events

### Detection Thresholds

Evolution detection uses these thresholds:

```python
EVOLUTION_THRESHOLDS = {
    'split': {
        'min_destinations': 2,        # At least 2 destination clusters
        'min_proportion': 0.2,        # Each destination gets ≥20% of units
        'min_confidence': 0.8         # High confidence required
    },
    'merge': {
        'min_sources': 2,             # At least 2 source clusters  
        'min_proportion': 0.2,        # Each source contributes ≥20% of units
        'min_confidence': 0.8         # High confidence required
    },
    'continuation': {
        'min_proportion': 0.8,        # ≥80% of units stay in cluster
        'max_centroid_drift': 0.3,    # Centroid moves <30%
        'min_confidence': 0.7         # Moderate confidence sufficient
    }
}
```

### Evolution Confidence Calculation

```python
def calculate_evolution_confidence(transition_data):
    """Calculate confidence in evolution detection."""
    
    # Factor 1: Proportion clarity (how clear the split is)
    proportions = list(transition_data['proportions'].values())
    proportion_clarity = 1 - np.std(proportions) if len(proportions) > 1 else 1.0
    
    # Factor 2: Unit count (more units = higher confidence)
    total_units = sum(transition_data['unit_counts'].values())
    unit_factor = min(1.0, total_units / 50)  # Normalize to 50 units
    
    # Factor 3: Centroid stability (similar centroids = higher confidence)
    similarity_factor = np.mean(list(transition_data['similarities'].values()))
    
    # Combine factors
    confidence = (
        proportion_clarity * 0.4 +    # 40% weight on clear proportions
        unit_factor * 0.3 +           # 30% weight on sufficient units
        similarity_factor * 0.3       # 30% weight on centroid similarity
    )
    
    return round(confidence, 3)
```

### Evolution Detection Algorithm

The evolution tracker compares cluster assignments between weeks:

```python
class EvolutionDetector:
    """Detects cluster evolution between clustering runs."""
    
    def detect_evolution(self, previous_assignments, current_assignments):
        """
        Detect evolution events by analyzing unit transitions.
        
        Args:
            previous_assignments: {unit_id: cluster_id} from previous week
            current_assignments: {unit_id: cluster_id} from current week
            
        Returns:
            List of evolution events
        """
        
        # Build transition matrix
        transitions = self._build_transition_matrix(
            previous_assignments, 
            current_assignments
        )
        
        evolution_events = []
        
        # Detect splits (1 cluster → many clusters)
        evolution_events.extend(self._detect_splits(transitions))
        
        # Detect merges (many clusters → 1 cluster)  
        evolution_events.extend(self._detect_merges(transitions))
        
        # Detect continuations (1 cluster → 1 cluster, mostly unchanged)
        evolution_events.extend(self._detect_continuations(transitions))
        
        return evolution_events
    
    def _build_transition_matrix(self, prev_assignments, curr_assignments):
        """Build matrix showing unit movements between clusters."""
        
        transitions = defaultdict(lambda: defaultdict(list))
        
        for unit_id in set(prev_assignments.keys()) | set(curr_assignments.keys()):
            prev_cluster = prev_assignments.get(unit_id, None)
            curr_cluster = curr_assignments.get(unit_id, None)
            
            if prev_cluster and curr_cluster:
                transitions[prev_cluster][curr_cluster].append(unit_id)
                
        return transitions
```

### Indexes for Evolution Relationships

```cypher
// Index for evolution type filtering
CREATE INDEX evolved_into_type_idx FOR ()-[r:EVOLVED_INTO]-() ON (r.evolution_type);

// Index for week-based evolution queries
CREATE INDEX evolved_into_week_idx FOR ()-[r:EVOLVED_INTO]-() ON (r.evolution_week);

// Composite index for type and week
CREATE INDEX evolved_into_type_week_idx FOR ()-[r:EVOLVED_INTO]-() ON (r.evolution_type, r.evolution_week);

// Index for high-confidence evolutions
CREATE INDEX evolved_into_confidence_idx FOR ()-[r:EVOLVED_INTO]-() ON (r.confidence);
```

### Evolution Query Patterns

#### Get Evolution Timeline for a Cluster
```cypher
MATCH path = (origin:Cluster)<-[:EVOLVED_INTO*]-(c:Cluster {id: $cluster_id})
RETURN path, length(path) as evolution_depth
ORDER BY evolution_depth DESC;
```

#### Find All Splits in a Time Period
```cypher
MATCH (c_old:Cluster)-[r:EVOLVED_INTO {evolution_type: "split"}]->(c_new:Cluster)
WHERE r.evolution_week >= $start_week AND r.evolution_week <= $end_week
RETURN 
    c_old.label as original_cluster,
    collect({
        new_cluster: c_new.label,
        proportion: r.proportion,
        unit_count: r.unit_count
    }) as split_results,
    r.evolution_week as week
ORDER BY r.evolution_week DESC;
```

#### Find Recent Merges
```cypher
MATCH (c_old:Cluster)-[r:EVOLVED_INTO {evolution_type: "merge"}]->(c_new:Cluster)
WHERE r.evolution_week >= $recent_week
WITH c_new, collect({
    source: c_old.label,
    proportion: r.proportion,
    confidence: r.confidence
}) as sources, r.evolution_week as week
RETURN c_new.label as merged_cluster, sources, week
ORDER BY week DESC;
```

#### Track Cluster Lineage
```cypher
MATCH (c:Cluster {id: $cluster_id})
OPTIONAL MATCH path = (c)-[:EVOLVED_INTO*]->(descendant:Cluster)
OPTIONAL MATCH ancestor_path = (ancestor:Cluster)-[:EVOLVED_INTO*]->(c)
RETURN 
    c.label as current_cluster,
    collect(DISTINCT descendant.label) as descendants,
    collect(DISTINCT ancestor.label) as ancestors;
```

#### Find Unstable Clusters (frequent evolution)
```cypher
MATCH (c:Cluster)-[r:EVOLVED_INTO]->()
WITH c, count(r) as evolution_count, collect(r.evolution_type) as evolution_types
WHERE evolution_count >= 3
RETURN 
    c.label as cluster,
    evolution_count,
    evolution_types,
    c.created_week as created
ORDER BY evolution_count DESC;
```

#### Get Evolution Statistics by Week
```cypher
MATCH ()-[r:EVOLVED_INTO]->()
WITH r.evolution_week as week, r.evolution_type as type, count(*) as count
RETURN week, collect({type: type, count: count}) as evolution_summary
ORDER BY week DESC;
```

### Validation Queries for Evolution

#### Check Evolution Proportions Sum to 1.0
```cypher
// For splits, proportions should sum to ~1.0
MATCH (c_old:Cluster)-[r:EVOLVED_INTO {evolution_type: "split"}]->()
WITH c_old, sum(r.proportion) as total_proportion
WHERE abs(total_proportion - 1.0) > 0.1  // Allow 10% tolerance
RETURN c_old.id, total_proportion;
```

#### Find Evolution Loops (invalid)
```cypher
// Clusters shouldn't evolve in loops
MATCH (c1:Cluster)-[:EVOLVED_INTO*]->(c2:Cluster)-[:EVOLVED_INTO*]->(c1)
RETURN c1.id, c2.id;
```

#### Check Evolution Confidence Distribution
```cypher
MATCH ()-[r:EVOLVED_INTO]->()
RETURN 
    r.evolution_type as type,
    avg(r.confidence) as avg_confidence,
    min(r.confidence) as min_confidence,
    max(r.confidence) as max_confidence,
    count(r) as total_events
ORDER BY type;
```

### Evolution Visualization Queries

#### Get Evolution Network for Visualization
```cypher
MATCH (c1:Cluster)-[r:EVOLVED_INTO]->(c2:Cluster)
WHERE r.evolution_week >= $start_week
RETURN {
    nodes: collect(DISTINCT {
        id: c1.id, 
        label: c1.label, 
        week: c1.created_week,
        size: c1.member_count
    }) + collect(DISTINCT {
        id: c2.id,
        label: c2.label, 
        week: c2.created_week,
        size: c2.member_count
    }),
    edges: collect({
        source: c1.id,
        target: c2.id,
        type: r.evolution_type,
        week: r.evolution_week,
        proportion: r.proportion,
        confidence: r.confidence
    })
};
```

#### Get Timeline Data for Evolution Visualization
```cypher
MATCH ()-[r:EVOLVED_INTO]->()
WITH r.evolution_week as week, r.evolution_type as type, 
     count(*) as event_count, avg(r.confidence) as avg_confidence
RETURN week, type, event_count, avg_confidence
ORDER BY week, type;
```

## Next Steps

This evolution tracking design provides the foundation for:

1. **Visualization query patterns** (Phase 2.5)
2. **Data migration strategy** (Phase 2.6)
3. **Complete schema documentation**
4. **Implementation planning**

The evolution schema enables comprehensive tracking of how knowledge topics naturally split, merge, and evolve over time, providing insights into content lifecycle patterns.