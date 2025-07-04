# Manual Clustering Guide

This document explains how to manually run clustering on existing data in the Neo4j database.

## Overview

The manual clustering command allows you to run semantic clustering on MeaningfulUnits that already exist in the database. This is useful when:
- You want to re-cluster data after changing clustering parameters
- Automatic clustering was disabled during episode processing
- You need to cluster data that was processed before clustering was implemented

**Important**: Each clustering run completely deletes all existing clusters and creates new ones from scratch. This ensures a clean slate and prevents database bloat from accumulating old cluster data.

## Usage

### Basic Command

```bash
./run_clustering.sh --podcast "The Mel Robbins Podcast"
```

### With Options

```bash
# Verbose output
./run_clustering.sh --podcast "The Mel Robbins Podcast" --verbose

# Force clustering even with insufficient data
./run_clustering.sh --podcast "My First Million" --force

# Both verbose and force
./run_clustering.sh -p "The Mel Robbins Podcast" -v -f
```

## How It Works

1. **Database Selection**: The command automatically selects the correct Neo4j database based on the podcast name from `podcasts.yaml`
   - "The Mel Robbins Podcast" → neo4j://localhost:7687
   - "My First Million" → neo4j://localhost:7688

2. **Data Validation**: Before clustering, the system checks:
   - Number of MeaningfulUnits with embeddings
   - Minimum data requirements for meaningful clusters
   - Existing clusters in the database

3. **Clustering Process**:
   - **Deletes all existing clusters** before creating new ones (clean slate approach)
   - Uses HDBSCAN algorithm with parameters from `clustering_config.yaml`
   - Groups similar MeaningfulUnits based on their embeddings
   - Generates descriptive labels for each cluster using LLM
   - Creates fresh Cluster nodes and IN_CLUSTER relationships in Neo4j

## Requirements

- Neo4j database must be running
- GEMINI_API_KEY environment variable must be set
- Sufficient MeaningfulUnits with embeddings in the database
- Podcast must be configured in `seeding_pipeline/config/podcasts.yaml`

## Troubleshooting

### "No MeaningfulUnits with embeddings found"
- Ensure episodes have been processed successfully
- Check that embedding generation was enabled during processing

### "Insufficient units for meaningful clustering"
- Process more episodes first, or
- Use `--force` flag to cluster anyway (may produce poor results)

### "Podcast not found in configuration"
- Check the exact podcast name in `podcasts.yaml`
- Names are case-sensitive

### Database Connection Failed
- Ensure Neo4j is running on the configured port
- Check NEO4J_USER and NEO4J_PASSWORD environment variables