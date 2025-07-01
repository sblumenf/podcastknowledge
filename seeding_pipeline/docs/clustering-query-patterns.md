# Clustering System Query Patterns

## Overview

This document provides comprehensive Cypher query patterns for the semantic clustering system. These queries support visualization, monitoring, analytics, and system operations.

## Table of Contents

1. [Visualization Queries](#visualization-queries)
2. [Content Discovery Queries](#content-discovery-queries)
3. [Evolution Analysis Queries](#evolution-analysis-queries)
4. [System Monitoring Queries](#system-monitoring-queries)
5. [Quality Assessment Queries](#quality-assessment-queries)
6. [Maintenance Queries](#maintenance-queries)
7. [Analytics Queries](#analytics-queries)

## Visualization Queries

### Get Cluster Overview for Dashboard

**Purpose**: Main visualization showing all active clusters with sizes and labels.

```cypher
MATCH (c:Cluster {status: 'active'})
OPTIONAL MATCH (c)<-[r:IN_CLUSTER {is_primary: true}]-(m:MeaningfulUnit)
WITH c, count(m) as member_count, avg(r.confidence) as avg_confidence
RETURN c.id as cluster_id,
       c.label as cluster_label,
       member_count,
       avg_confidence,
       c.created_week as created_week
ORDER BY member_count DESC
LIMIT 50;
```

### Get Cluster Network for Force-Directed Visualization

**Purpose**: Network graph showing clusters and their evolution relationships.

```cypher
MATCH (c1:Cluster)-[r:EVOLVED_INTO]->(c2:Cluster)
WHERE r.evolution_week >= $start_week AND r.confidence >= 0.7
RETURN {
    nodes: collect(DISTINCT {
        id: c1.id,
        label: c1.label,
        size: c1.member_count,
        week: c1.created_week,
        status: c1.status
    }) + collect(DISTINCT {
        id: c2.id,
        label: c2.label,
        size: c2.member_count,
        week: c2.created_week,
        status: c2.status
    }),
    edges: collect({
        source: c1.id,
        target: c2.id,
        type: r.evolution_type,
        week: r.evolution_week,
        proportion: r.proportion,
        confidence: r.confidence
    })
} as network_data;
```

### Get Hierarchical Cluster Tree

**Purpose**: Tree-like structure for hierarchical visualization.

```cypher
MATCH (c:Cluster {status: 'active'})
OPTIONAL MATCH (c)<-[:IN_CLUSTER {is_primary: true}]-(m:MeaningfulUnit)<-[:CONTAINS]-(e:Episode)
WITH c, count(DISTINCT m) as unit_count, count(DISTINCT e) as episode_count
RETURN c.label as cluster_name,
       unit_count,
       episode_count,
       c.avg_confidence as confidence,
       c.created_week as created_week
ORDER BY unit_count DESC;
```

### Get Temporal Heatmap Data

**Purpose**: Cluster activity over time for heatmap visualization.

```cypher
MATCH (c:Cluster)<-[r:IN_CLUSTER {is_primary: true}]-(m:MeaningfulUnit)<-[:CONTAINS]-(e:Episode)
WITH c.label as cluster_label, 
     substring(e.published_date, 0, 7) as year_month,
     count(m) as activity_count
RETURN cluster_label, year_month, activity_count
ORDER BY cluster_label, year_month;
```

## Content Discovery Queries

### Find MeaningfulUnits in a Cluster

**Purpose**: Get all content for a specific cluster - core functionality for user content discovery.

```cypher
MATCH (c:Cluster {id: $cluster_id})<-[r:IN_CLUSTER {is_primary: true}]-(m:MeaningfulUnit)<-[:CONTAINS]-(e:Episode)
RETURN m.id as unit_id,
       m.summary as summary,
       m.start_time as start_time,
       m.end_time as end_time,
       e.title as episode_title,
       e.published_date as episode_date,
       e.id as episode_id,
       r.confidence as cluster_confidence
ORDER BY r.confidence DESC, e.published_date DESC;
```

### Search Clusters by Label

**Purpose**: Find clusters matching search terms.

```cypher
MATCH (c:Cluster {status: 'active'})
WHERE toLower(c.label) CONTAINS toLower($search_term)
OPTIONAL MATCH (c)<-[:IN_CLUSTER {is_primary: true}]-(m:MeaningfulUnit)
WITH c, count(m) as member_count
RETURN c.id as cluster_id,
       c.label as cluster_label,
       member_count,
       c.avg_confidence as avg_confidence,
       c.created_week as created_week
ORDER BY member_count DESC;
```

### Find Related Clusters

**Purpose**: Discover clusters that share content or evolution history.

```cypher
MATCH (c1:Cluster {id: $cluster_id})

// Find clusters sharing MeaningfulUnits (through evolution)
OPTIONAL MATCH (c1)<-[:IN_CLUSTER]-(m:MeaningfulUnit)-[:IN_CLUSTER]->(c2:Cluster)
WHERE c1 <> c2 AND c2.status = 'active'

// Find clusters with evolution relationships
OPTIONAL MATCH (c1)-[:EVOLVED_INTO*..2]-(c3:Cluster)
WHERE c3.status = 'active'

// Find clusters with similar labels (basic text similarity)
OPTIONAL MATCH (c4:Cluster {status: 'active'})
WHERE c4 <> c1 AND 
      any(word in split(toLower(c1.label), ' ') 
          WHERE toLower(c4.label) CONTAINS word)

WITH c1, collect(DISTINCT c2) + collect(DISTINCT c3) + collect(DISTINCT c4) as related_clusters
UNWIND related_clusters as related
RETURN DISTINCT related.id as cluster_id,
       related.label as cluster_label,
       related.member_count as size
ORDER BY size DESC
LIMIT 10;
```

### Cross-Episode Content Discovery

**Purpose**: Find all episodes that discuss a specific cluster topic.

```cypher
MATCH (c:Cluster {id: $cluster_id})<-[r:IN_CLUSTER {is_primary: true}]-(m:MeaningfulUnit)<-[:CONTAINS]-(e:Episode)
WITH e, count(m) as units_in_episode, avg(r.confidence) as avg_confidence
RETURN e.id as episode_id,
       e.title as episode_title,
       e.published_date as published_date,
       units_in_episode,
       avg_confidence
ORDER BY units_in_episode DESC, avg_confidence DESC;
```

## Evolution Analysis Queries

### Get Complete Evolution Timeline

**Purpose**: Track how a cluster has evolved over time.

```cypher
MATCH path = (origin:Cluster)<-[:EVOLVED_INTO*]-(current:Cluster {id: $cluster_id})
WITH nodes(path) as evolution_nodes, relationships(path) as evolution_rels
UNWIND range(0, size(evolution_nodes)-1) as i
WITH evolution_nodes[i] as cluster, 
     CASE WHEN i > 0 THEN evolution_rels[i-1] ELSE null END as evolution_rel
RETURN cluster.id as cluster_id,
       cluster.label as cluster_label,
       cluster.created_week as week,
       cluster.member_count as size,
       cluster.status as status,
       evolution_rel.evolution_type as how_evolved,
       evolution_rel.proportion as proportion,
       evolution_rel.confidence as confidence
ORDER BY cluster.created_week;
```

### Find All Evolution Events in Time Period

**Purpose**: Monitor system evolution activity.

```cypher
MATCH (c1:Cluster)-[r:EVOLVED_INTO]->(c2:Cluster)
WHERE r.evolution_week >= $start_week AND r.evolution_week <= $end_week
RETURN r.evolution_week as week,
       r.evolution_type as type,
       c1.label as from_cluster,
       c2.label as to_cluster,
       r.proportion as proportion,
       r.confidence as confidence,
       r.unit_count as units_affected
ORDER BY r.evolution_week DESC, r.confidence DESC;
```

### Detect Evolution Patterns

**Purpose**: Identify trending evolution behaviors.

```cypher
MATCH ()-[r:EVOLVED_INTO]->()
WHERE r.evolution_week >= $start_week
WITH r.evolution_type as type, 
     r.evolution_week as week,
     count(*) as event_count,
     avg(r.confidence) as avg_confidence
RETURN type, week, event_count, avg_confidence
ORDER BY week DESC, event_count DESC;
```

### Find Cluster Lineage

**Purpose**: Get complete ancestry and descendants of a cluster.

```cypher
MATCH (c:Cluster {id: $cluster_id})

// Find ancestors
OPTIONAL MATCH ancestor_path = (ancestor:Cluster)-[:EVOLVED_INTO*]->(c)
WITH c, collect(DISTINCT {
    id: ancestor.id, 
    label: ancestor.label, 
    week: ancestor.created_week,
    relationship: 'ancestor'
}) as ancestors

// Find descendants  
OPTIONAL MATCH descendant_path = (c)-[:EVOLVED_INTO*]->(descendant:Cluster)
WITH c, ancestors, collect(DISTINCT {
    id: descendant.id,
    label: descendant.label, 
    week: descendant.created_week,
    relationship: 'descendant'
}) as descendants

RETURN c.id as cluster_id,
       c.label as cluster_label,
       c.created_week as current_week,
       ancestors,
       descendants;
```

## System Monitoring Queries

### Clustering Health Check

**Purpose**: Overall system health for monitoring dashboards.

```cypher
MATCH (cs:ClusteringState)
WHERE cs.timestamp >= datetime() - duration({days: 7})
WITH cs.status as status, count(cs) as count, max(cs.timestamp) as last_run
RETURN status, count, last_run
ORDER BY status;
```

### Get Latest Clustering Statistics

**Purpose**: Current system state for monitoring.

```cypher
MATCH (cs:ClusteringState {status: 'completed'})
WITH cs ORDER BY cs.timestamp DESC LIMIT 1

MATCH (c:Cluster {status: 'active'})
OPTIONAL MATCH (c)<-[:IN_CLUSTER {is_primary: true}]-(m:MeaningfulUnit)

RETURN cs.week as latest_week,
       cs.timestamp as last_clustering,
       cs.n_clusters as total_clusters,
       cs.n_outliers as outliers,
       cs.outlier_ratio as outlier_percentage,
       cs.quality_score as quality_score,
       cs.execution_time_seconds as execution_time,
       count(DISTINCT c) as active_clusters,
       count(m) as total_assigned_units;
```

### Performance Trending

**Purpose**: Track clustering performance over time.

```cypher
MATCH (cs:ClusteringState {status: 'completed'})
WHERE cs.timestamp >= datetime() - duration({days: 90})
RETURN cs.week as week,
       cs.execution_time_seconds as execution_time,
       cs.total_units as units_processed,
       round(cs.execution_time_seconds / cs.total_units, 4) as seconds_per_unit,
       cs.quality_score as quality_score
ORDER BY cs.timestamp;
```

### Quality Issues Detection

**Purpose**: Identify clustering runs with quality problems.

```cypher
MATCH (cs:ClusteringState {status: 'completed'})
WHERE cs.quality_score < 0.7 OR cs.outlier_ratio > 0.2
RETURN cs.week as week,
       cs.quality_score as quality_score,
       cs.outlier_ratio as outlier_ratio,
       cs.n_clusters as cluster_count,
       cs.n_outliers as outlier_count,
       CASE 
         WHEN cs.quality_score < 0.7 THEN 'Low Quality'
         WHEN cs.outlier_ratio > 0.2 THEN 'High Outliers'
         ELSE 'Unknown Issue'
       END as issue_type
ORDER BY cs.timestamp DESC
LIMIT 20;
```

## Quality Assessment Queries

### Cluster Size Distribution

**Purpose**: Analyze cluster size patterns for quality assessment.

```cypher
MATCH (c:Cluster {status: 'active'})
OPTIONAL MATCH (c)<-[:IN_CLUSTER {is_primary: true}]-(m:MeaningfulUnit)
WITH c, count(m) as size
WITH size, count(c) as cluster_count
RETURN size, cluster_count
ORDER BY size;
```

### Confidence Score Analysis

**Purpose**: Assess assignment confidence distribution.

```cypher
MATCH ()-[r:IN_CLUSTER {is_primary: true}]->()
WITH round(r.confidence, 1) as confidence_bucket, count(*) as assignment_count
RETURN confidence_bucket, assignment_count
ORDER BY confidence_bucket;
```

### Low Confidence Assignments

**Purpose**: Identify potentially problematic assignments for review.

```cypher
MATCH (m:MeaningfulUnit)-[r:IN_CLUSTER {is_primary: true}]->(c:Cluster)
WHERE r.confidence < 0.6
RETURN m.id as unit_id,
       m.summary as summary,
       c.label as cluster_label,
       r.confidence as confidence,
       r.cluster_distance as distance
ORDER BY r.confidence ASC
LIMIT 50;
```

### Outlier Analysis

**Purpose**: Understand which content becomes outliers.

```cypher
MATCH (m:MeaningfulUnit)<-[:CONTAINS]-(e:Episode)
WHERE NOT EXISTS {
    MATCH (m)-[:IN_CLUSTER {is_primary: true}]->()
}
RETURN m.id as outlier_unit_id,
       m.summary as summary,
       e.title as episode_title,
       e.published_date as episode_date
ORDER BY e.published_date DESC
LIMIT 20;
```

## Maintenance Queries

### Archive Old ClusteringState Records

**Purpose**: Clean up old clustering run records.

```cypher
// Archive states older than 1 year, keeping minimum 52 records
MATCH (cs:ClusteringState {status: 'completed'})
WHERE cs.timestamp < datetime() - duration({weeks: 52})
WITH cs ORDER BY cs.timestamp DESC
SKIP 52
DETACH DELETE cs
RETURN count(*) as archived_count;
```

### Clean Failed Clustering Runs

**Purpose**: Remove old failed clustering attempts.

```cypher
MATCH (cs:ClusteringState {status: 'failed'})
WHERE cs.timestamp < datetime() - duration({days: 30})
DETACH DELETE cs
RETURN count(*) as cleaned_count;
```

### Archive Inactive Clusters

**Purpose**: Mark old clusters as archived rather than deleting.

```cypher
MATCH (c:Cluster)
WHERE c.status IN ['split', 'merged'] 
  AND c.created_week < $archival_week
SET c.status = 'archived'
RETURN count(c) as archived_clusters;
```

### Validate Data Integrity

**Purpose**: Check for data consistency issues.

```cypher
// Check for units with multiple primary assignments
MATCH (m:MeaningfulUnit)-[r:IN_CLUSTER {is_primary: true}]->()
WITH m, count(r) as assignment_count
WHERE assignment_count > 1
RETURN m.id as problematic_unit, assignment_count

UNION

// Check for clusters with invalid status
MATCH (c:Cluster)
WHERE NOT c.status IN ['active', 'split', 'merged', 'archived']
RETURN c.id as problematic_cluster, c.status as invalid_status

UNION

// Check for evolution proportion mismatches in splits
MATCH (c:Cluster)-[r:EVOLVED_INTO {evolution_type: 'split'}]->()
WITH c, sum(r.proportion) as total_proportion
WHERE abs(total_proportion - 1.0) > 0.1
RETURN c.id as split_cluster, total_proportion as proportion_sum;
```

## Analytics Queries

### Topic Evolution Trends

**Purpose**: Analyze how topics change over time.

```cypher
MATCH ()-[r:EVOLVED_INTO]->()
WHERE r.evolution_week >= $analysis_start_week
WITH r.evolution_week as week, 
     r.evolution_type as type,
     count(*) as event_count
RETURN week, 
       sum(CASE WHEN type = 'split' THEN event_count ELSE 0 END) as splits,
       sum(CASE WHEN type = 'merge' THEN event_count ELSE 0 END) as merges,
       sum(CASE WHEN type = 'continuation' THEN event_count ELSE 0 END) as continuations
ORDER BY week;
```

### Content Velocity Analysis

**Purpose**: Measure how quickly new content is being clustered.

```cypher
MATCH (e:Episode)-[:CONTAINS]->(m:MeaningfulUnit)-[r:IN_CLUSTER {is_primary: true}]->(c:Cluster)
WITH substring(e.published_date, 0, 7) as year_month,
     count(DISTINCT e) as episodes_processed,
     count(m) as units_clustered,
     count(DISTINCT c) as clusters_involved
RETURN year_month,
       episodes_processed,
       units_clustered,
       clusters_involved,
       round(toFloat(units_clustered) / episodes_processed, 1) as avg_units_per_episode
ORDER BY year_month;
```

### Cluster Stability Metrics

**Purpose**: Identify most/least stable clusters.

```cypher
MATCH (c:Cluster)
OPTIONAL MATCH (c)-[r:EVOLVED_INTO]->()
WITH c, count(r) as evolution_count
RETURN c.label as cluster_label,
       c.created_week as created_week,
       c.member_count as size,
       evolution_count,
       CASE 
         WHEN evolution_count = 0 THEN 'Very Stable'
         WHEN evolution_count <= 2 THEN 'Stable'  
         WHEN evolution_count <= 5 THEN 'Moderate'
         ELSE 'Unstable'
       END as stability_rating
ORDER BY evolution_count DESC, c.member_count DESC;
```

### Cross-Episode Topic Coverage

**Purpose**: Analyze how topics span across episodes.

```cypher
MATCH (c:Cluster {status: 'active'})<-[:IN_CLUSTER {is_primary: true}]-(m:MeaningfulUnit)<-[:CONTAINS]-(e:Episode)
WITH c, count(DISTINCT e) as episode_count, count(m) as unit_count
WHERE episode_count > 1  // Multi-episode topics only
RETURN c.label as cluster_label,
       episode_count,
       unit_count,
       round(toFloat(unit_count) / episode_count, 1) as avg_units_per_episode
ORDER BY episode_count DESC, unit_count DESC;
```

## Usage Examples

### Dashboard Data Query

**Purpose**: Single query to populate main dashboard.

```cypher
// Get dashboard overview data
CALL {
    // Active clusters summary
    MATCH (c:Cluster {status: 'active'})
    OPTIONAL MATCH (c)<-[:IN_CLUSTER {is_primary: true}]-(m:MeaningfulUnit)
    RETURN count(DISTINCT c) as active_clusters, count(m) as total_units
} 

CALL {
    // Recent evolution activity
    MATCH ()-[r:EVOLVED_INTO]->()
    WHERE r.evolution_week >= $recent_week
    RETURN count(r) as recent_evolutions
}

CALL {
    // Latest clustering run status
    MATCH (cs:ClusteringState)
    WITH cs ORDER BY cs.timestamp DESC LIMIT 1
    RETURN cs.status as last_status, cs.quality_score as last_quality
}

RETURN active_clusters, total_units, recent_evolutions, last_status, last_quality;
```

### Content Search Workflow

**Purpose**: Multi-step content discovery process.

```cypher
// Step 1: Find clusters matching search
MATCH (c:Cluster {status: 'active'})
WHERE toLower(c.label) CONTAINS toLower($search_term)
WITH c ORDER BY c.member_count DESC LIMIT 5

// Step 2: Get content from top clusters
MATCH (c)<-[r:IN_CLUSTER {is_primary: true}]-(m:MeaningfulUnit)<-[:CONTAINS]-(e:Episode)
RETURN c.label as cluster_label,
       collect({
           unit_id: m.id,
           summary: m.summary,
           episode_title: e.title,
           confidence: r.confidence
       })[0..10] as top_content  // Limit to 10 per cluster
ORDER BY c.member_count DESC;
```

## Performance Considerations

### Query Optimization Tips

1. **Use LIMIT**: Always limit results for UI queries
2. **Index Utilization**: Ensure queries use appropriate indexes
3. **Parameterize**: Use parameters for repeated queries
4. **Profile**: Use `PROFILE` to optimize slow queries

### Recommended Indexes

All indexes from the schema documentation should be created:

```cypher
// Essential indexes for query performance
CREATE INDEX cluster_status_idx FOR (c:Cluster) ON (c.status);
CREATE INDEX in_cluster_primary_idx FOR ()-[r:IN_CLUSTER]-() ON (r.is_primary);
CREATE INDEX evolved_into_week_idx FOR ()-[r:EVOLVED_INTO]-() ON (r.evolution_week);
CREATE INDEX clustering_state_status_idx FOR (cs:ClusteringState) ON (cs.status);
```

This comprehensive query reference provides all the patterns needed for visualization, content discovery, system monitoring, and analytics in the semantic clustering system.