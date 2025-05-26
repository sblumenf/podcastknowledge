# Runbook: High Memory Usage

## Description
Troubleshoot and resolve high memory usage issues in the Podcast Knowledge Graph Pipeline.

## Symptoms
- [ ] Memory usage above 80% for extended period
- [ ] Out of Memory (OOM) kills in pod events
- [ ] Performance degradation
- [ ] Alert: "High Memory Usage" triggered

## Impact
- **Severity**: High
- **Affected Components**: Processing pipeline, API responsiveness
- **User Impact**: Slow processing, potential failures

## Prerequisites
- Kubernetes cluster access
- Monitoring dashboard access
- Permission to scale deployments

## Resolution Steps

### 1. Verify the Issue
```bash
# Check current memory usage
kubectl top pods -n podcast-kg

# Check for OOM kills
kubectl get events -n podcast-kg | grep -i oom

# View pod resource usage
kubectl describe pod <pod-name> -n podcast-kg | grep -A 5 "Limits:"
```

### 2. Identify Memory Consumers
```bash
# Connect to pod and check process memory
kubectl exec -it <pod-name> -n podcast-kg -- /bin/bash

# Inside pod - check memory usage
ps aux --sort=-%mem | head -20
```

### 3. Immediate Mitigation

#### Option A: Increase Memory Limits
```bash
# Edit deployment to increase memory
kubectl edit deployment podcast-kg-pipeline -n podcast-kg

# Update resources section:
# resources:
#   limits:
#     memory: "12Gi"  # Increased from 8Gi
#   requests:
#     memory: "8Gi"   # Increased from 4Gi
```

#### Option B: Scale Horizontally
```bash
# Add more pods to distribute load
kubectl scale deployment podcast-kg-pipeline --replicas=5 -n podcast-kg

# Verify scaling
kubectl get pods -n podcast-kg
```

### 4. Clear Caches
```bash
# Clear Redis cache if needed
kubectl exec -it deployment/redis -n podcast-kg -- redis-cli FLUSHDB

# Clear application caches
kubectl exec -it deployment/podcast-kg-pipeline -n podcast-kg -- \
  python -c "from src.utils.memory import clear_caches; clear_caches()"
```

### 5. Analyze Memory Leaks
```bash
# Enable memory profiling
kubectl set env deployment/podcast-kg-pipeline \
  PODCAST_KG_MEMORY_PROFILE=true -n podcast-kg

# Collect memory dump after 10 minutes
kubectl exec -it <pod-name> -n podcast-kg -- \
  python -m memory_profiler scripts/analyze_memory.py

# Download memory profile
kubectl cp <pod-name>:/app/memory_profile.bin ./memory_profile.bin -n podcast-kg
```

## Long-term Solutions

### 1. Optimize Code
- Review large data structures
- Implement streaming for large files
- Use generators instead of lists
- Clear unused objects explicitly

### 2. Tune Garbage Collection
```python
# Add to application startup
import gc
gc.set_threshold(700, 10, 10)  # More aggressive GC
```

### 3. Implement Memory Limits
```python
# Add memory monitoring
from src.utils.memory import MemoryMonitor

monitor = MemoryMonitor(max_memory_gb=6.0)
monitor.check_memory_usage()  # Raises if exceeded
```

### 4. Configure Batch Sizes
```yaml
# In config.yml
processing:
  batch_size: 5  # Reduce from 10
  max_segment_length: 2000  # Reduce from 3000
```

## Monitoring Setup

### Create Memory Alerts
```yaml
# Prometheus alert rule
- alert: HighMemoryUsage
  expr: container_memory_usage_bytes / container_spec_memory_limit_bytes > 0.8
  for: 5m
  annotations:
    summary: "High memory usage in {{ $labels.pod }}"
    runbook: "docs/runbooks/06-high-memory-usage.md"
```

### Grafana Dashboard
- Import dashboard ID: 12345
- Key panels: Memory usage over time, GC frequency, Cache hit rate

## Prevention
- Regular memory profiling in CI/CD
- Load testing with memory monitoring
- Implement memory budgets per component
- Review and optimize large data operations

## Root Cause Analysis Template
- **Date**: 
- **Duration**: 
- **Root Cause**: 
- **Data Volume**: 
- **Fix Applied**: 
- **Prevention**: 

## Related Runbooks
- [10-performance-degradation.md](10-performance-degradation.md)
- [05-scaling.md](05-scaling.md)
- [07-processing-failures.md](07-processing-failures.md)