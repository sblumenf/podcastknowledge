# Podcast Knowledge Graph Pipeline - Monitoring

This directory contains the monitoring infrastructure for the Podcast Knowledge Graph Pipeline, including Prometheus metrics collection, Grafana dashboards, and alerting configurations.

## Components

### Prometheus
- Collects metrics from the podcast pipeline application
- Configured to scrape metrics every 15 seconds
- Stores data for 15 days with a maximum size of 50GB
- Includes service discovery for Kubernetes environments

### Grafana
- Provides visualization dashboards for monitoring
- Two pre-configured dashboards:
  - **Podcast Knowledge Graph Pipeline**: Main operational dashboard
  - **Podcast KG - SLO Dashboard**: Service Level Objective monitoring

### Alertmanager
- Handles alerts from Prometheus
- Routes alerts based on severity and team ownership
- Configured with email and Slack notifications

### SLO/SLI Framework
- Service Level Objectives define reliability targets
- Service Level Indicators measure actual performance
- Error budget tracking and burn rate alerts
- Multi-window alerting for fast and slow burns

## Dashboards

### Main Pipeline Dashboard
The main dashboard (`podcast-kg-pipeline.json`) includes:

1. **Overview Section**
   - Total episodes processed
   - Current success rate (5-minute window)
   - Queue size
   - Error rate

2. **Episode Processing**
   - Processing rate over time (successful vs failed)
   - Processing latency percentiles (p50, p95, p99)

3. **System Resources**
   - CPU usage by pod
   - Memory usage by pod

4. **Provider Health**
   - API call rates by provider
   - Provider latency (p95)
   - Provider error table
   - Service status indicators

5. **Processing Quality**
   - Extraction quality scores
   - Entities extracted per episode

6. **Graph Database**
   - Node creation rate by type
   - Relationship creation rate by type
   - Total nodes/relationships distribution

7. **Queue Metrics**
   - Queue depth over time
   - Queue wait time percentiles

### SLO Dashboard
The SLO dashboard (`podcast-kg-slo.json`) provides comprehensive SLO monitoring:

1. **Availability SLO**
   - Current SLI vs 99.5% target
   - Error budget remaining gauge
   - Multi-window compliance tracking

2. **Error Budget Tracking**
   - Burn rate visualization (1h, 6h, 24h)
   - Fast/slow burn alert indicators
   - Time until budget exhaustion

3. **Latency SLOs**
   - Episode processing: 95% within 5 minutes
   - API response: 99% within 1 second
   - Historical trends and violations

4. **Quality SLOs**
   - Transcription accuracy: 85% minimum
   - Entity extraction: 5+ entities per episode
   - Provider reliability by service

5. **Composite SLOs**
   - Overall reliability score
   - Data quality score
   - SLO compliance summary table

## Setup Instructions

### Using Docker Compose

1. Ensure the podcast-kg-network exists:
   ```bash
   docker network create podcast-kg-network
   ```

2. Start the monitoring stack:
   ```bash
   docker-compose -f docker-compose.monitoring.yml up -d
   ```

3. Access the services:
   - Prometheus: http://localhost:9090
   - Grafana: http://localhost:3000 (default: admin/admin)
   - Alertmanager: http://localhost:9093

### Kubernetes Deployment

For Kubernetes deployments, use the Prometheus Operator or adapt the configurations for Helm charts.

## Metrics Collected

The application exposes the following key metrics:

- `podcast_kg_episodes_processed_total`: Total episodes successfully processed
- `podcast_kg_episodes_failed_total`: Total episodes that failed processing
- `podcast_kg_processing_duration_seconds`: Episode processing duration histogram
- `podcast_kg_provider_calls_total`: Provider API call counter
- `podcast_kg_provider_errors_total`: Provider error counter
- `podcast_kg_provider_latency_seconds`: Provider API latency histogram
- `podcast_kg_memory_usage_bytes`: Current memory usage
- `podcast_kg_cpu_usage_percent`: Current CPU usage percentage
- `podcast_kg_nodes_created_total`: Graph nodes created by type
- `podcast_kg_relationships_created_total`: Graph relationships created by type
- `podcast_kg_extraction_quality_score`: Quality score histogram
- `podcast_kg_entities_per_episode`: Summary of entities per episode
- `podcast_kg_queue_size`: Current processing queue size
- `podcast_kg_queue_wait_seconds`: Queue wait time histogram

## Alerts

Configured alerts include:

### Critical Alerts
- ServiceDown: Pipeline service unavailable
- CriticalMemoryUsage: Memory usage above 7.5GB
- Neo4jConnectionFailures: Database connection issues
- SLOViolation: Availability below 99%

### Warning Alerts
- HighErrorRate: Error rate above 10%
- HighMemoryUsage: Memory usage above 6GB
- HighCPUUsage: CPU usage above 80%
- ProviderHighErrorRate: Provider error rate high
- SlowProcessing: p95 processing time above 5 minutes
- ProcessingQueueBacklog: Queue size above 100

## Customization

### Adding New Metrics

1. Add metric definitions in `src/api/metrics.py`
2. Update dashboard JSON files to include new panels
3. Add corresponding alerts in `prometheus-alerts.yml`

### Modifying Dashboards

1. Import dashboard JSON into Grafana
2. Make changes using Grafana UI
3. Export updated JSON and replace the file

### Alert Configuration

1. Edit `prometheus-alerts.yml` for alert rules
2. Update `alertmanager.yml` for routing and notifications
3. Restart Prometheus and Alertmanager

## Troubleshooting

### No Metrics Appearing
- Check that the application is exposing metrics on `/metrics`
- Verify Prometheus can reach the application endpoint
- Check Prometheus targets page for scrape errors

### Dashboard Not Loading
- Ensure Grafana datasource is configured correctly
- Verify Prometheus is running and accessible
- Check Grafana logs for errors

### Alerts Not Firing
- Verify alert rules syntax in Prometheus
- Check Alertmanager configuration and logs
- Ensure webhook URLs are accessible

## Best Practices

1. **Regular Review**: Review dashboards weekly to identify trends
2. **Alert Tuning**: Adjust thresholds based on actual performance
3. **Capacity Planning**: Use metrics for resource planning
4. **SLO Tracking**: Monitor SLO compliance and adjust targets
5. **Documentation**: Keep runbook links in alerts updated

## SLO Management

### Configuration

SLOs are defined in `config/slo.yml` with the following structure:

```yaml
slos:
  - name: availability
    objective: 99.5  # Target percentage
    windows:
      - duration: 1h
      - duration: 24h
      - duration: 30d
    error_budget:
      monthly_budget_minutes: 216
```

### SLI Queries

Pre-computed SLI queries are defined in `sli-queries.yml` as Prometheus recording rules:

```promql
# Availability SLI
sli:availability:ratio = 
  sum(rate(podcast_kg_episodes_processed_total[5m])) / 
  (sum(rate(podcast_kg_episodes_processed_total[5m])) + 
   sum(rate(podcast_kg_episodes_failed_total[5m])))
```

### Error Budget Alerts

Multi-window burn rate alerts in `slo-alerts.yml`:

- **Fast Burn**: 2% in 1h + 1% in 6h → Page immediately
- **Slow Burn**: 5% in 6h + 2% in 24h → Create ticket
- **Budget Low**: < 20% remaining → Freeze non-critical changes
- **Budget Exhausted**: 0% remaining → Incident response

### API Endpoints

Access SLO status via API:

- `GET /api/v1/slo/status` - Current SLO status and error budget
- `GET /api/v1/slo/config` - SLO definitions and targets
- `GET /api/v1/slo/report` - Compliance report for time window
- `POST /api/v1/slo/register` - Register new SLO dynamically

### Integration

Use the SLO tracking module in your code:

```python
from src.api.slo_tracking import get_slo_tracker

tracker = get_slo_tracker()

# Track episode processing
with tracker.track_episode_processing(episode_id, podcast_id) as episode:
    # Processing logic
    episode.set_quality_score(0.92)

# Track entity extraction
tracker.track_entity_extraction(episode_id, entity_count=8)
```

For detailed SLO management guidance, see `docs/guides/slo_management.rst`.