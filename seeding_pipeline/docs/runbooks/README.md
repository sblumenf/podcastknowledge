# Operational Runbooks

This directory contains runbooks for common operational tasks and incident response procedures for the Podcast Knowledge Graph Pipeline.

## Available Runbooks

### 🚀 Deployment & Startup
- [01-deployment.md](01-deployment.md) - Deploy the application
- [02-startup-shutdown.md](02-startup-shutdown.md) - Start and stop procedures

### 🔧 Maintenance
- [03-backup-restore.md](03-backup-restore.md) - Backup and restore procedures
- [04-update-rollback.md](04-update-rollback.md) - Update and rollback procedures
- [05-scaling.md](05-scaling.md) - Scaling the application

### 🚨 Incident Response
- [06-high-memory-usage.md](06-high-memory-usage.md) - Troubleshoot high memory usage
- [07-processing-failures.md](07-processing-failures.md) - Handle processing failures
- [08-database-issues.md](08-database-issues.md) - Resolve database problems
- [09-api-errors.md](09-api-errors.md) - Fix API integration errors
- [10-performance-degradation.md](10-performance-degradation.md) - Address performance issues

### 📊 Monitoring & Diagnostics
- [11-health-checks.md](11-health-checks.md) - Monitor system health
- [12-log-analysis.md](12-log-analysis.md) - Analyze logs for issues
- [13-metrics-monitoring.md](13-metrics-monitoring.md) - Monitor key metrics

### 🔄 Recovery Procedures
- [14-checkpoint-recovery.md](14-checkpoint-recovery.md) - Recover from checkpoints
- [15-data-recovery.md](15-data-recovery.md) - Recover lost data
- [16-disaster-recovery.md](16-disaster-recovery.md) - Full disaster recovery

## Quick Reference

### Emergency Contacts
- **On-Call Engineer**: See PagerDuty
- **Platform Team**: platform@example.com
- **Database Admin**: dba@example.com

### Critical Commands

```bash
# Check system health
curl http://localhost:8000/health

# View recent logs
kubectl logs -f deployment/podcast-kg-pipeline -n podcast-kg --tail=100

# Check pod status
kubectl get pods -n podcast-kg

# Emergency shutdown
kubectl scale deployment podcast-kg-pipeline --replicas=0 -n podcast-kg
```

### Common Issues Quick Fixes

| Issue | Quick Fix | Runbook |
|-------|-----------|---------|
| Out of Memory | Scale up pods or increase memory limits | [06-high-memory-usage.md](06-high-memory-usage.md) |
| Processing Stuck | Check checkpoints and restart | [07-processing-failures.md](07-processing-failures.md) |
| Neo4j Down | Check connection and restart database | [08-database-issues.md](08-database-issues.md) |
| API Rate Limited | Check cache and reduce request rate | [09-api-errors.md](09-api-errors.md) |
| Slow Processing | Check resource usage and scale | [10-performance-degradation.md](10-performance-degradation.md) |

## Runbook Standards

All runbooks follow this format:

1. **Title & Description**: Clear problem statement
2. **Symptoms**: How to identify the issue
3. **Impact**: What's affected
4. **Prerequisites**: Required access/tools
5. **Resolution Steps**: Numbered steps to fix
6. **Verification**: How to confirm resolution
7. **Prevention**: How to avoid recurrence
8. **Related**: Links to related runbooks

## Contributing

When adding new runbooks:
1. Use the template in `TEMPLATE.md`
2. Number sequentially
3. Update this README
4. Test all commands
5. Get peer review