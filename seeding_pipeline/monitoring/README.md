# Podcast Knowledge Graph Pipeline - Monitoring

This directory contains monitoring configuration for the Podcast Knowledge Graph Pipeline.

## Overview

The pipeline uses internal metrics collection for monitoring performance and health. All metrics are collected in-memory and exposed via the `/metrics` endpoint in Prometheus format for compatibility, but no external monitoring systems are required.

## Metrics Collected

The application collects the following key metrics internally:

### Processing Metrics
- `podcast_kg_episodes_processed_total`: Total episodes successfully processed
- `podcast_kg_episodes_failed_total`: Total episodes that failed processing
- `podcast_kg_processing_duration_seconds`: Episode processing duration histogram

### Provider Metrics
- `podcast_kg_provider_calls_total`: Provider API call counter
- `podcast_kg_provider_errors_total`: Provider error counter
- `podcast_kg_provider_latency_seconds`: Provider API latency histogram

### Resource Metrics
- `podcast_kg_memory_usage_bytes`: Current memory usage
- `podcast_kg_cpu_usage_percent`: Current CPU usage percentage

### Graph Metrics
- `podcast_kg_nodes_created_total`: Graph nodes created by type
- `podcast_kg_relationships_created_total`: Graph relationships created by type

### Quality Metrics
- `podcast_kg_extraction_quality_score`: Quality score histogram
- `podcast_kg_entities_per_episode`: Summary of entities per episode

### Queue Metrics
- `podcast_kg_queue_size`: Current processing queue size
- `podcast_kg_queue_wait_seconds`: Queue wait time histogram

## Accessing Metrics

### Via API Endpoint
Metrics are available in Prometheus format at:
```
GET /metrics
```

### Via Summary Endpoint
A human-readable summary is available at:
```
GET /api/v1/stats
```

## Using Metrics

### In Code
```python
from src.api.metrics import get_metrics_collector, track_duration

collector = get_metrics_collector()

# Increment counter
collector.episodes_processed.inc()

# Record duration
@track_duration(metric_name="processing_duration", stage="extraction")
def extract_knowledge():
    # Your code here
    pass

# Get summary
summary = collector.get_summary()
```

### Logging
All important metrics are automatically logged at regular intervals. Check application logs for performance tracking.

## Best Practices

1. **Monitor Logs**: Key metrics are logged automatically
2. **Check Summary**: Use `/api/v1/stats` for quick health checks
3. **Resource Monitoring**: CPU and memory usage are tracked automatically
4. **Error Tracking**: Failed episodes are logged with details

## Simple Health Monitoring

For basic health monitoring without external systems:

1. Check application logs for errors
2. Monitor the `/health` endpoint
3. Review metrics summary at `/api/v1/stats`
4. Set up log aggregation if needed

## Configuration

No external monitoring configuration is required. The application automatically collects and exposes metrics.