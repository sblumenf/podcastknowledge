# Clustering User Guide

## Overview

The podcast knowledge system now uses **semantic clustering** instead of topic extraction to organize content. This guide explains what changed, why it's better, and how to discover knowledge using the new cluster-based approach.

## What Changed: Topics → Clusters

### Before (Topic System)
- Episodes were tagged with topics like "Technology" or "Business"
- Searching for "AI" returned ALL content from episodes mentioning AI anywhere
- You'd get 100+ irrelevant segments mixed with the 5 you actually wanted
- Topics were inconsistent: "AI" vs "Artificial Intelligence" vs "Machine Learning"

### After (Cluster System)  
- Individual conversation units cluster together based on semantic similarity
- Searching clusters returns ONLY content actually discussing that topic
- Related discussions from different episodes naturally group together
- No manual normalization needed - math handles variations automatically

## Key Benefits

### 1. Precision
**Before**: Click "Cars" → Get all 30 units from episodes mentioning cars → Only 3 actually about cars
**After**: Click "Electric Vehicles" cluster → Get only units actually discussing EVs from all episodes

### 2. Cross-Episode Intelligence
Related content connects across episodes automatically:
- "Tesla factory updates" from Episode 5
- "EV charging infrastructure" from Episode 12  
- "Battery technology advances" from Episode 18
- All in the same "Electric Vehicles" cluster

### 3. Knowledge Evolution Tracking
Watch how topics evolve over time:
- Week 1-10: Single "Cars" cluster
- Week 11: Splits into "Electric Cars" and "Traditional Cars"
- Week 20: "Electric Cars" splits into "Tesla" and "Other EVs"

## How to Use Clusters

### Finding Cluster Content

```cypher
// Get all active clusters with sizes
MATCH (c:Cluster {status: 'active'})
OPTIONAL MATCH (c)<-[:IN_CLUSTER]-(m:MeaningfulUnit)
RETURN c.label as cluster_name, 
       c.id as cluster_id,
       count(m) as size
ORDER BY size DESC
```

### Viewing Cluster Contents

```cypher
// Get all content for a specific cluster
MATCH (c:Cluster {label: 'Machine Learning'})
MATCH (c)<-[:IN_CLUSTER]-(m:MeaningfulUnit)<-[:CONTAINS]-(e:Episode)
RETURN m.summary as discussion,
       e.title as episode,
       e.published_date as date
ORDER BY date DESC
```

### Finding Related Clusters

```cypher
// Find clusters related to "AI"
MATCH (c:Cluster)
WHERE c.label CONTAINS 'AI' OR c.label CONTAINS 'Artificial' OR c.label CONTAINS 'Machine'
AND c.status = 'active'
RETURN c.label, c.id
ORDER BY c.label
```

## Understanding Cluster Evolution

### Evolution Types

**Splits**: One cluster becomes multiple clusters
- Indicates topic differentiation
- Example: "Technology" → "AI" + "Hardware" + "Software"

**Merges**: Multiple clusters become one cluster  
- Indicates topic convergence
- Example: "Electric Cars" + "Tesla" → "EV Technology"

**Continuations**: Cluster remains stable
- Indicates persistent knowledge domain
- Example: "Climate Change" cluster stays consistent over time

### Querying Evolution

```cypher
// See how a cluster evolved
MATCH path = (origin:Cluster)<-[:EVOLVED_INTO*]-(c:Cluster {label: 'Electric Vehicles'})
RETURN path

// Find all evolution events from a time period
MATCH (c1:Cluster)-[r:EVOLVED_INTO]->(c2:Cluster)
WHERE r.week >= '2024-W15' AND r.week <= '2024-W20'
RETURN c1.label as from_cluster,
       c2.label as to_cluster,
       r.type as evolution_type,
       r.week as when_occurred
```

## Best Practices

### 1. Browse by Cluster Size
Start with larger clusters for broad topics, then explore smaller clusters for specific discussions.

### 2. Use Evolution to Find Trends
Check recent split events to identify emerging subtopics.

### 3. Cross-Reference Related Clusters
Look for clusters with similar labels or shared evolution history.

### 4. Time-Based Analysis
Filter clusters by creation week to see how knowledge develops over time.

## Common Use Cases

### Research Mode: "Find everything about X"
1. Search cluster labels for your topic
2. Get all MeaningfulUnits in matching clusters
3. Review content chronologically

### Discovery Mode: "What's this podcast about?"
1. Query clusters by size
2. Review top 10-15 cluster labels
3. Explore interesting clusters in detail

### Trend Analysis: "How has topic X evolved?"
1. Find clusters related to topic X
2. Query evolution relationships
3. Track splits/merges over time

## Technical Notes

- Clusters are created using HDBSCAN algorithm on 768-dimensional embeddings
- New clusters are generated automatically after processing episodes
- All data stored in Neo4j - no external files or systems
- Evolution tracking runs automatically - no manual maintenance needed

## Getting Help

If you encounter issues:
1. Check cluster counts and sizes using the queries above
2. Verify recent episodes have been processed
3. Look at logs for clustering statistics
4. Consult the maintenance guide for parameter tuning

The clustering system is designed to improve automatically as more content is added, providing increasingly precise knowledge organization.