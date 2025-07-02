# Clustering System Documentation

## Overview

The clustering system groups MeaningfulUnits by semantic similarity using HDBSCAN clustering on embeddings.

## What It Does

1. **Extracts embeddings** from MeaningfulUnits stored in Neo4j
2. **Performs HDBSCAN clustering** to group semantically similar units
3. **Generates human-readable labels** for each cluster using LLM
4. **Updates Neo4j** with cluster assignments

## How to Use

Run clustering after processing episodes:

```python
from src.clustering import SemanticClusteringSystem

# Initialize (typically done in main.py)
clustering_system = SemanticClusteringSystem(neo4j_service, llm_service)

# Run clustering
result = clustering_system.run_clustering()

# Check results
if result['status'] == 'success':
    print(f"Created {result['stats']['n_clusters']} clusters")
    print(f"Clustered {result['stats']['total_units']} units")
```

## Neo4j Schema

### Nodes

- **Cluster**: Represents a semantic cluster
  - `id`: Unique identifier (e.g., "cluster_0")
  - `label`: Human-readable label
  - `member_count`: Number of units in cluster
  - `centroid`: Embedding centroid (768-dim vector)
  - `status`: Always "active"
  - `created_timestamp`: When cluster was created

### Relationships

- **IN_CLUSTER**: Links MeaningfulUnit to Cluster
  - `confidence`: HDBSCAN membership confidence (0.0-1.0)
  - `is_primary`: Always true
  - `assigned_at`: Timestamp of assignment

## Example Queries

Find all clusters:
```cypher
MATCH (c:Cluster)
RETURN c.id, c.label, c.member_count
ORDER BY c.member_count DESC
```

Find units in a specific cluster:
```cypher
MATCH (m:MeaningfulUnit)-[:IN_CLUSTER]->(c:Cluster {label: "AI Ethics"})
RETURN m.summary, m.themes
```

Find clusters for an episode:
```cypher
MATCH (e:Episode {id: "episode_123"})<-[:PART_OF]-(m:MeaningfulUnit)-[:IN_CLUSTER]->(c:Cluster)
RETURN DISTINCT c.label, count(m) as unit_count
ORDER BY unit_count DESC
```

## Configuration

Edit `config/clustering_config.yaml` to adjust:
- `min_cluster_size`: Minimum units per cluster
- `min_samples`: Core point neighborhood size
- `epsilon`: Cluster merge distance threshold