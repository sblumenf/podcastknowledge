# Clustering System Maintenance Guide

This guide provides comprehensive instructions for maintaining the semantic clustering system in production. It covers monitoring, troubleshooting, optimization, and regular maintenance tasks to ensure optimal performance and reliability.

## Table of Contents

1. [System Overview](#system-overview)
2. [Monitoring Setup](#monitoring-setup)
3. [Regular Maintenance Tasks](#regular-maintenance-tasks)
4. [Performance Monitoring](#performance-monitoring)
5. [Troubleshooting Common Issues](#troubleshooting-common-issues)
6. [Optimization Recommendations](#optimization-recommendations)
7. [System Health Checks](#system-health-checks)
8. [Emergency Procedures](#emergency-procedures)
9. [Performance Tuning](#performance-tuning)
10. [Backup and Recovery](#backup-and-recovery)

## System Overview

The semantic clustering system consists of several key components:

- **Semantic Clustering System**: Core HDBSCAN-based clustering engine
- **Neo4j Database**: Graph storage for clusters, relationships, and metadata
- **LLM Service**: Gemini API for cluster label generation
- **Evolution Tracking**: System for tracking cluster changes over time
- **Monitoring**: Performance and quality metrics collection

### Key Files and Locations

```
src/clustering/semantic_clustering.py          # Core clustering engine
src/clustering/cluster_evolution.py           # Evolution tracking
src/clustering/cluster_labeling.py            # Label generation
clustering_config.yaml                        # Configuration file
docs/clustering_user_guide.md                 # User documentation
docs/clustering_rollback_plan.md              # Emergency rollback
```

## Monitoring Setup

### 1. Log Monitoring

The clustering system generates structured logs with performance metrics:

```bash
# Monitor clustering execution logs
tail -f /var/log/clustering/semantic_clustering.log

# Monitor performance metrics
grep "Clustering completed" /var/log/clustering/*.log | tail -20

# Monitor quality warnings
grep "⚠️" /var/log/clustering/*.log
```

### 2. Key Metrics to Monitor

#### Performance Metrics
- **Execution Time**: Should complete 1000 units in <60 seconds
- **Memory Usage**: Should not exceed 2GB increase during clustering
- **Throughput**: Target >10 units/second processing speed

#### Quality Metrics
- **Outlier Ratio**: Should stay below 30%
- **Cluster Count**: Should be reasonable for data size (3-20 typically)
- **Label Generation Success**: Should be >95% for production data

#### System Health Metrics
- **Database Connections**: Monitor Neo4j connection pool health
- **API Rate Limits**: Track Gemini API usage and limits
- **Disk Usage**: Monitor embedding storage growth

### 3. Automated Monitoring Setup

Create monitoring scripts for regular health checks:

```bash
# Create monitoring cron job
# Add to crontab -e:
0 */6 * * * /path/to/clustering_health_check.sh >> /var/log/clustering/health.log 2>&1
```

**clustering_health_check.sh**:
```bash
#!/bin/bash

echo "[$(date)] Starting clustering health check..."

# Check database connectivity
python3 -c "
from src.storage.graph_storage import GraphStorageService
try:
    db = GraphStorageService('bolt://localhost:7687', 'neo4j', 'password')
    result = db.query('MATCH (n) RETURN count(n) LIMIT 1')
    print('✅ Database connectivity: OK')
    db.close()
except Exception as e:
    print(f'❌ Database connectivity: FAILED - {e}')
"

# Check recent clustering performance
python3 -c "
import logging
from pathlib import Path

log_file = Path('/var/log/clustering/semantic_clustering.log')
if log_file.exists():
    with open(log_file) as f:
        lines = f.readlines()[-100:]  # Last 100 lines
    
    perf_lines = [l for l in lines if 'Clustering completed' in l]
    if perf_lines:
        print('✅ Recent clustering activity: OK')
        print(f'   Last execution: {perf_lines[-1].strip()}')
    else:
        print('⚠️  No recent clustering activity found')
else:
    print('❌ Clustering log file not found')
"

echo "[$(date)] Health check completed"
```

## Regular Maintenance Tasks

### Daily Tasks

#### 1. Check System Health
```bash
# Run health check script
./clustering_health_check.sh

# Check log file sizes
du -h /var/log/clustering/*.log

# Monitor disk usage
df -h /var/lib/neo4j
```

#### 2. Review Performance Metrics
```bash
# Check recent clustering performance
grep "Clustering completed" /var/log/clustering/*.log | tail -10

# Look for warnings or errors
grep -E "(WARNING|ERROR|⚠️|❌)" /var/log/clustering/*.log | tail -20
```

### Weekly Tasks

#### 1. Performance Analysis
```bash
# Run performance test
python3 performance_test.py

# Review clustering quality trends
python3 -c "
from src.storage.graph_storage import GraphStorageService
db = GraphStorageService('bolt://localhost:7687', 'neo4j', 'password')

# Check recent cluster quality
query = '''
MATCH (c:Cluster)
WHERE c.created_at > datetime() - duration('P7D')  // Last 7 days
RETURN 
    count(c) as new_clusters,
    avg(size((c)<-[:IN_CLUSTER]-())) as avg_cluster_size,
    min(size((c)<-[:IN_CLUSTER]-())) as min_cluster_size,
    max(size((c)<-[:IN_CLUSTER]-())) as max_cluster_size
'''

result = db.query(query)
if result:
    print('📊 Weekly Cluster Quality Report:')
    print(f'   New clusters: {result[0][\"new_clusters\"]}')
    print(f'   Avg size: {result[0][\"avg_cluster_size\"]:.1f}')
    print(f'   Size range: {result[0][\"min_cluster_size\"]}-{result[0][\"max_cluster_size\"]}')

db.close()
"
```

#### 2. Database Maintenance
```bash
# Neo4j database statistics
echo "SHOW DATABASE YIELD name, currentStatus, currentPrimary, requestedStatus;" | cypher-shell

# Check database size and growth
echo "
MATCH (n) 
RETURN labels(n)[0] as node_type, count(n) as count 
ORDER BY count DESC;
" | cypher-shell

# Check for orphaned nodes (shouldn't be many)
echo "
MATCH (n) 
WHERE NOT (n)--() AND NOT n:Podcast 
RETURN labels(n)[0] as orphan_type, count(n) as count;
" | cypher-shell
```

### Monthly Tasks

#### 1. Performance Optimization Review
```bash
# Run comprehensive performance test
python3 simulated_performance_test.py

# Analyze parameter effectiveness
python3 -c "
from src.storage.graph_storage import GraphStorageService
import json

db = GraphStorageService('bolt://localhost:7687', 'neo4j', 'password')

# Check clustering parameter effectiveness over time
query = '''
MATCH (s:ClusteringState)
WHERE s.timestamp > datetime() - duration('P30D')
RETURN s.timestamp, s.parameters, s.stats
ORDER BY s.timestamp DESC
LIMIT 10
'''

results = db.query(query)
if results:
    print('📈 Recent Clustering Parameter Performance:')
    for result in results:
        params = json.loads(result['parameters'])
        stats = json.loads(result['stats'])
        print(f'   {result[\"timestamp\"]}: min_size={params.get(\"min_cluster_size\", \"N/A\")}, '
              f'clusters={stats.get(\"n_clusters\", \"N/A\")}, '
              f'outliers={stats.get(\"outlier_ratio\", 0):.1%}')

db.close()
"
```

#### 2. Storage Cleanup
```bash
# Clean old log files (keep last 30 days)
find /var/log/clustering -name "*.log" -mtime +30 -delete

# Clean old clustering state (keep last 50 states)
python3 -c "
from src.storage.graph_storage import GraphStorageService

db = GraphStorageService('bolt://localhost:7687', 'neo4j', 'password')

# Keep only the most recent 50 clustering states
query = '''
MATCH (s:ClusteringState)
WITH s ORDER BY s.timestamp DESC
SKIP 50
DETACH DELETE s
'''

result = db.query(query)
print('🧹 Cleaned old clustering states')

db.close()
"
```

## Performance Monitoring

### Key Performance Indicators (KPIs)

#### 1. Execution Time Monitoring
```python
# Monitor clustering execution time trends
def check_execution_time_trends():
    from src.storage.graph_storage import GraphStorageService
    import json
    from datetime import datetime, timedelta
    
    db = GraphStorageService('bolt://localhost:7687', 'neo4j', 'password')
    
    query = """
    MATCH (s:ClusteringState)
    WHERE s.timestamp > datetime() - duration('P7D')
    RETURN s.timestamp, s.execution_time
    ORDER BY s.timestamp DESC
    """
    
    results = db.query(query)
    if results:
        times = [float(r['execution_time']) for r in results]
        avg_time = sum(times) / len(times)
        max_time = max(times)
        
        print(f"📊 Execution Time (Last 7 days):")
        print(f"   Average: {avg_time:.1f}s")
        print(f"   Maximum: {max_time:.1f}s")
        print(f"   Samples: {len(times)}")
        
        if avg_time > 30:
            print("⚠️  Average execution time is high - consider optimization")
        if max_time > 60:
            print("❌ Maximum execution time exceeds threshold")
    
    db.close()
```

#### 2. Quality Metrics Monitoring
```python
# Monitor clustering quality over time
def check_quality_trends():
    from src.storage.graph_storage import GraphStorageService
    import json
    
    db = GraphStorageService('bolt://localhost:7687', 'neo4j', 'password')
    
    query = """
    MATCH (s:ClusteringState)
    WHERE s.timestamp > datetime() - duration('P7D')
    RETURN s.timestamp, s.stats
    ORDER BY s.timestamp DESC
    """
    
    results = db.query(query)
    if results:
        outlier_ratios = []
        cluster_counts = []
        
        for result in results:
            stats = json.loads(result['stats'])
            outlier_ratios.append(stats.get('outlier_ratio', 0))
            cluster_counts.append(stats.get('n_clusters', 0))
        
        avg_outlier_ratio = sum(outlier_ratios) / len(outlier_ratios)
        avg_clusters = sum(cluster_counts) / len(cluster_counts)
        
        print(f"📊 Quality Metrics (Last 7 days):")
        print(f"   Avg outlier ratio: {avg_outlier_ratio:.1%}")
        print(f"   Avg clusters: {avg_clusters:.1f}")
        
        if avg_outlier_ratio > 0.3:
            print("⚠️  High outlier ratio - consider parameter tuning")
        if avg_clusters < 3:
            print("⚠️  Low cluster count - may indicate under-clustering")
    
    db.close()
```

### Performance Alerts

Set up alerts for performance degradation:

```bash
# Create performance alert script
cat > clustering_performance_alert.py << 'EOF'
#!/usr/bin/env python3
"""
Performance alert system for clustering maintenance.
Checks key metrics and sends alerts when thresholds are exceeded.
"""

import smtplib
from email.mime.text import MimeText
from src.storage.graph_storage import GraphStorageService
import json
import sys

def check_performance_alerts():
    alerts = []
    
    db = GraphStorageService('bolt://localhost:7687', 'neo4j', 'password')
    
    # Check recent execution time
    query = """
    MATCH (s:ClusteringState)
    WHERE s.timestamp > datetime() - duration('PT24H')
    RETURN s.execution_time, s.stats
    ORDER BY s.timestamp DESC
    LIMIT 10
    """
    
    results = db.query(query)
    if results:
        exec_times = [float(r['execution_time']) for r in results]
        avg_time = sum(exec_times) / len(exec_times)
        
        if avg_time > 45:  # Alert threshold
            alerts.append(f"High execution time: {avg_time:.1f}s average")
        
        # Check outlier ratios
        outlier_ratios = []
        for result in results:
            stats = json.loads(result['stats'])
            outlier_ratios.append(stats.get('outlier_ratio', 0))
        
        avg_outlier = sum(outlier_ratios) / len(outlier_ratios)
        if avg_outlier > 0.35:  # Alert threshold
            alerts.append(f"High outlier ratio: {avg_outlier:.1%}")
    
    # Check database connectivity
    try:
        test_query = "MATCH (n) RETURN count(n) LIMIT 1"
        db.query(test_query)
    except Exception as e:
        alerts.append(f"Database connectivity issue: {e}")
    
    db.close()
    
    if alerts:
        send_alerts(alerts)
        return False
    return True

def send_alerts(alerts):
    # Configure your alert system here
    # This example just prints to console
    print("🚨 CLUSTERING SYSTEM ALERTS:")
    for alert in alerts:
        print(f"   - {alert}")
    
    # Add email/Slack/webhook notifications as needed

if __name__ == "__main__":
    success = check_performance_alerts()
    sys.exit(0 if success else 1)
EOF

chmod +x clustering_performance_alert.py

# Add to crontab for hourly checks:
# 0 * * * * /path/to/clustering_performance_alert.py
```

## Troubleshooting Common Issues

### Issue 1: High Outlier Ratio (>30%)

**Symptoms:**
- Many MeaningfulUnits are not assigned to clusters
- Warnings in logs: "HIGH OUTLIER RATIO"

**Diagnosis:**
```bash
# Check current outlier ratio
python3 -c "
from src.clustering.semantic_clustering import SemanticClusteringSystem
from src.storage.graph_storage import GraphStorageService
from src.services.llm_service import LLMService
import os

db = GraphStorageService('bolt://localhost:7687', 'neo4j', 'password')
llm = LLMService(os.environ['GEMINI_API_KEY'], 'gemini-1.5-flash-002')
clustering_config = {'clustering': {'min_cluster_size_formula': 'sqrt'}}
system = SemanticClusteringSystem(db, llm, clustering_config)

result = system.run_clustering()
if result['status'] == 'success':
    print(f'Outlier ratio: {result[\"stats\"][\"outlier_ratio\"]:.1%}')
    print(f'Clusters: {result[\"stats\"][\"n_clusters\"]}')
"
```

**Solutions:**
1. **Reduce min_cluster_size**:
   ```yaml
   # In clustering_config.yaml
   clustering:
     min_cluster_size_formula: "sqrt_small"  # or "fixed"
     min_cluster_size_fixed: 3
   ```

2. **Adjust epsilon parameter**:
   ```yaml
   clustering:
     epsilon: 0.2  # Reduce from 0.3 for tighter clusters
   ```

3. **Check data quality**:
   ```python
   # Verify embeddings are reasonable
   query = """
   MATCH (m:MeaningfulUnit)
   WHERE m.embedding IS NULL
   RETURN count(m) as missing_embeddings
   """
   ```

### Issue 2: Clustering Takes Too Long (>60s for 1000 units)

**Symptoms:**
- Clustering execution time exceeds performance criteria
- System appears slow or unresponsive

**Diagnosis:**
```bash
# Run performance test
python3 performance_test.py

# Check system resources during clustering
top -p $(pgrep -f semantic_clustering) 
```

**Solutions:**
1. **Optimize HDBSCAN parameters**:
   ```yaml
   clustering:
     core_dist_n_jobs: 4  # Use multiple cores
     min_samples: 2       # Reduce from 3
   ```

2. **Use dimensionality reduction**:
   ```python
   # Add PCA preprocessing for large datasets
   from sklearn.decomposition import PCA
   
   # In semantic_clustering.py, before HDBSCAN:
   if len(embeddings) > 1000:
       pca = PCA(n_components=384)  # Reduce from 768
       embeddings = pca.fit_transform(embeddings)
   ```

3. **Batch processing**:
   ```python
   # Process in smaller batches for very large datasets
   batch_size = 500
   for i in range(0, len(units), batch_size):
       batch = units[i:i+batch_size]
       # Process batch
   ```

### Issue 3: Label Generation Failures

**Symptoms:**
- Clusters created without labels
- API errors in logs related to Gemini

**Diagnosis:**
```bash
# Check API connectivity
python3 -c "
from src.services.llm_service import LLMService
import os

try:
    llm = LLMService(os.environ['GEMINI_API_KEY'], 'gemini-1.5-flash-002')
    response = llm.generate_response('Test message')
    print('✅ LLM service connectivity OK')
except Exception as e:
    print(f'❌ LLM service failed: {e}')
"

# Check API rate limits
grep "rate limit" /var/log/clustering/*.log
```

**Solutions:**
1. **Check API key and quotas**:
   ```bash
   # Verify API key is valid
   curl -H "Authorization: Bearer $GEMINI_API_KEY" \
        "https://generativelanguage.googleapis.com/v1beta/models"
   ```

2. **Implement retry logic**:
   ```python
   # In cluster_labeling.py
   import time
   from tenacity import retry, stop_after_attempt, wait_exponential
   
   @retry(stop=stop_after_attempt(3), wait=wait_exponential(multiplier=1, min=4, max=10))
   def generate_label_with_retry(self, cluster_texts):
       return self.llm_service.generate_response(prompt)
   ```

3. **Use fallback labeling**:
   ```python
   # Generate simple labels from common words if LLM fails
   def generate_fallback_label(self, cluster_texts):
       from collections import Counter
       import re
       
       words = []
       for text in cluster_texts:
           words.extend(re.findall(r'\b\w+\b', text.lower()))
       
       common_words = Counter(words).most_common(3)
       return f"Topic: {', '.join([w[0] for w in common_words])}"
   ```

### Issue 4: Memory Usage Too High

**Symptoms:**
- Memory usage exceeds 2GB during clustering
- System performance degrades
- Out of memory errors

**Solutions:**
1. **Process in batches**:
   ```python
   # Modify semantic_clustering.py
   def process_large_dataset(self, max_memory_mb=1500):
       import psutil
       
       while True:
           memory_usage = psutil.Process().memory_info().rss / 1024 / 1024
           if memory_usage > max_memory_mb:
               # Process smaller batch
               batch_size = max(100, batch_size // 2)
           
           # Process batch
   ```

2. **Clear intermediate data**:
   ```python
   # Explicitly clean up large objects
   del embeddings_array
   import gc
   gc.collect()
   ```

3. **Use memory-efficient data structures**:
   ```python
   # Use numpy arrays instead of lists for embeddings
   import numpy as np
   embeddings = np.array(embedding_list, dtype=np.float32)
   ```

### Issue 5: Evolution Tracking Not Working

**Symptoms:**
- No EVOLVED_INTO relationships created
- Cluster history not preserved

**Diagnosis:**
```bash
# Check for evolution relationships
echo "MATCH ()-[r:EVOLVED_INTO]->() RETURN count(r) as evolution_count;" | cypher-shell

# Check clustering state history
echo "MATCH (s:ClusteringState) RETURN count(s) as state_count ORDER BY s.timestamp DESC;" | cypher-shell
```

**Solutions:**
1. **Verify evolution tracking is enabled**:
   ```yaml
   # In clustering_config.yaml
   clustering:
     enable_evolution_tracking: true
     min_similarity_threshold: 0.3
   ```

2. **Check clustering state storage**:
   ```python
   # Verify state is being saved
   query = """
   MATCH (s:ClusteringState)
   RETURN s.timestamp, s.cluster_count
   ORDER BY s.timestamp DESC LIMIT 5
   """
   ```

## Optimization Recommendations

### 1. Parameter Tuning

**Optimal parameters for different data sizes:**

```yaml
# For small datasets (<500 units)
clustering:
  min_cluster_size_formula: "fixed"
  min_cluster_size_fixed: 3
  min_samples: 2
  epsilon: 0.2

# For medium datasets (500-2000 units)  
clustering:
  min_cluster_size_formula: "sqrt_small"
  min_samples: 3
  epsilon: 0.3

# For large datasets (>2000 units)
clustering:
  min_cluster_size_formula: "sqrt"
  min_samples: 5
  epsilon: 0.4
  core_dist_n_jobs: 4
```

### 2. Performance Optimization

**Database Optimization:**
```bash
# Neo4j performance tuning
# Add to neo4j.conf:
dbms.memory.heap.initial_size=2G
dbms.memory.heap.max_size=4G
dbms.memory.pagecache.size=2G

# Create optimal indexes
echo "CREATE INDEX meaningful_unit_embedding IF NOT EXISTS FOR (m:MeaningfulUnit) ON (m.embedding);" | cypher-shell
echo "CREATE INDEX cluster_id_index IF NOT EXISTS FOR (c:Cluster) ON (c.id);" | cypher-shell
```

**LLM Service Optimization:**
```python
# Use faster model for batch processing
llm_service = LLMService(
    api_key=api_key,
    model_name="gemini-1.5-flash-002",  # Faster than full model
    max_tokens=1000,  # Limit for faster responses
    temperature=0.1   # Lower for more consistent labels
)
```

### 3. Storage Optimization

**Embedding Storage:**
```python
# Compress embeddings for storage
import numpy as np

def compress_embedding(embedding):
    # Convert to float16 for 50% storage savings
    return np.array(embedding, dtype=np.float16).tolist()

def decompress_embedding(compressed):
    # Convert back to float32 for computation
    return np.array(compressed, dtype=np.float32)
```

**Database Cleanup:**
```cypher
// Remove old clustering states (keep last 20)
MATCH (s:ClusteringState)
WITH s ORDER BY s.timestamp DESC
SKIP 20
DETACH DELETE s;

// Remove orphaned cluster nodes
MATCH (c:Cluster)
WHERE NOT (c)<-[:IN_CLUSTER]-()
DETACH DELETE c;
```

## System Health Checks

### Comprehensive Health Check Script

```python
#!/usr/bin/env python3
"""
Comprehensive system health check for clustering system.
"""

import os
import sys
import time
import psutil
from pathlib import Path
from src.storage.graph_storage import GraphStorageService
from src.services.llm_service import LLMService

def run_health_check():
    """Run comprehensive system health check."""
    print("🏥 CLUSTERING SYSTEM HEALTH CHECK")
    print("=" * 50)
    
    checks = [
        check_database_connectivity,
        check_llm_service,
        check_disk_space,
        check_memory_usage,
        check_log_files,
        check_cluster_quality,
        check_recent_activity
    ]
    
    results = {}
    for check in checks:
        try:
            result = check()
            results[check.__name__] = result
            status = "✅" if result['status'] else "❌"
            print(f"{status} {result['name']}: {result['message']}")
        except Exception as e:
            results[check.__name__] = {'status': False, 'message': str(e)}
            print(f"❌ {check.__name__}: Failed - {e}")
    
    # Overall health
    healthy_checks = sum(1 for r in results.values() if r['status'])
    total_checks = len(results)
    health_percentage = (healthy_checks / total_checks) * 100
    
    print(f"\n📊 Overall Health: {healthy_checks}/{total_checks} ({health_percentage:.0f}%)")
    
    if health_percentage >= 90:
        print("🎉 System is healthy!")
    elif health_percentage >= 70:
        print("⚠️  System has minor issues")
    else:
        print("🚨 System requires attention")
    
    return health_percentage >= 70

def check_database_connectivity():
    """Check Neo4j database connectivity."""
    try:
        db = GraphStorageService('bolt://localhost:7687', 'neo4j', 'password')
        result = db.query("MATCH (n) RETURN count(n) LIMIT 1")
        db.close()
        
        return {
            'status': True,
            'name': 'Database Connectivity',
            'message': 'Connected successfully'
        }
    except Exception as e:
        return {
            'status': False,
            'name': 'Database Connectivity', 
            'message': f'Failed: {e}'
        }

def check_llm_service():
    """Check LLM service connectivity."""
    try:
        api_key = os.environ.get('GEMINI_API_KEY')
        if not api_key:
            return {
                'status': False,
                'name': 'LLM Service',
                'message': 'API key not configured'
            }
        
        llm = LLMService(api_key, 'gemini-1.5-flash-002')
        # Simple test call
        response = llm.generate_response('Test message', max_tokens=10)
        
        return {
            'status': True,
            'name': 'LLM Service',
            'message': 'API responding'
        }
    except Exception as e:
        return {
            'status': False,
            'name': 'LLM Service',
            'message': f'Failed: {e}'
        }

def check_disk_space():
    """Check disk space usage."""
    try:
        usage = psutil.disk_usage('/')
        percent_used = (usage.used / usage.total) * 100
        
        if percent_used > 90:
            status = False
            message = f'Critical: {percent_used:.1f}% used'
        elif percent_used > 80:
            status = False
            message = f'Warning: {percent_used:.1f}% used'
        else:
            status = True
            message = f'OK: {percent_used:.1f}% used'
        
        return {
            'status': status,
            'name': 'Disk Space',
            'message': message
        }
    except Exception as e:
        return {
            'status': False,
            'name': 'Disk Space',
            'message': f'Failed: {e}'
        }

def check_memory_usage():
    """Check system memory usage."""
    try:
        memory = psutil.virtual_memory()
        percent_used = memory.percent
        
        if percent_used > 90:
            status = False
            message = f'Critical: {percent_used:.1f}% used'
        elif percent_used > 80:
            status = False
            message = f'Warning: {percent_used:.1f}% used'
        else:
            status = True
            message = f'OK: {percent_used:.1f}% used'
        
        return {
            'status': status,
            'name': 'Memory Usage',
            'message': message
        }
    except Exception as e:
        return {
            'status': False,
            'name': 'Memory Usage',
            'message': f'Failed: {e}'
        }

def check_log_files():
    """Check log file status and sizes."""
    try:
        log_dir = Path('/var/log/clustering')
        if not log_dir.exists():
            log_dir = Path('./logs')  # Fallback
        
        if not log_dir.exists():
            return {
                'status': False,
                'name': 'Log Files',
                'message': 'Log directory not found'
            }
        
        log_files = list(log_dir.glob('*.log'))
        total_size = sum(f.stat().st_size for f in log_files) / 1024 / 1024  # MB
        
        if total_size > 1000:  # >1GB
            status = False
            message = f'Large log files: {total_size:.1f}MB'
        else:
            status = True
            message = f'OK: {len(log_files)} files, {total_size:.1f}MB'
        
        return {
            'status': status,
            'name': 'Log Files',
            'message': message
        }
    except Exception as e:
        return {
            'status': False,
            'name': 'Log Files',
            'message': f'Failed: {e}'
        }

def check_cluster_quality():
    """Check recent clustering quality metrics."""
    try:
        db = GraphStorageService('bolt://localhost:7687', 'neo4j', 'password')
        
        # Check recent clustering state
        query = """
        MATCH (s:ClusteringState)
        WHERE s.timestamp > datetime() - duration('P1D')
        RETURN s.stats
        ORDER BY s.timestamp DESC
        LIMIT 1
        """
        
        result = db.query(query)
        if not result:
            return {
                'status': False,
                'name': 'Cluster Quality',
                'message': 'No recent clustering data'
            }
        
        import json
        stats = json.loads(result[0]['stats'])
        outlier_ratio = stats.get('outlier_ratio', 0)
        n_clusters = stats.get('n_clusters', 0)
        
        if outlier_ratio > 0.4:
            status = False
            message = f'High outlier ratio: {outlier_ratio:.1%}'
        elif n_clusters < 2:
            status = False
            message = f'Too few clusters: {n_clusters}'
        else:
            status = True
            message = f'OK: {n_clusters} clusters, {outlier_ratio:.1%} outliers'
        
        db.close()
        return {
            'status': status,
            'name': 'Cluster Quality',
            'message': message
        }
    except Exception as e:
        return {
            'status': False,
            'name': 'Cluster Quality',
            'message': f'Failed: {e}'
        }

def check_recent_activity():
    """Check for recent clustering activity."""
    try:
        db = GraphStorageService('bolt://localhost:7687', 'neo4j', 'password')
        
        query = """
        MATCH (s:ClusteringState)
        RETURN s.timestamp
        ORDER BY s.timestamp DESC
        LIMIT 1
        """
        
        result = db.query(query)
        if not result:
            return {
                'status': False,
                'name': 'Recent Activity',
                'message': 'No clustering activity found'
            }
        
        from datetime import datetime, timezone
        last_activity = result[0]['timestamp']
        
        # Parse Neo4j datetime
        if hasattr(last_activity, 'to_native'):
            last_time = last_activity.to_native()
        else:
            last_time = datetime.fromisoformat(str(last_activity).replace('Z', '+00:00'))
        
        time_diff = datetime.now(timezone.utc) - last_time
        hours_ago = time_diff.total_seconds() / 3600
        
        if hours_ago > 48:  # No activity in 2 days
            status = False
            message = f'No activity for {hours_ago:.1f} hours'
        else:
            status = True
            message = f'Last activity: {hours_ago:.1f} hours ago'
        
        db.close()
        return {
            'status': status,
            'name': 'Recent Activity',
            'message': message
        }
    except Exception as e:
        return {
            'status': False,
            'name': 'Recent Activity',
            'message': f'Failed: {e}'
        }

if __name__ == "__main__":
    healthy = run_health_check()
    sys.exit(0 if healthy else 1)
```

## Emergency Procedures

### System Down Procedures

1. **Check System Status**:
   ```bash
   # Check if services are running
   systemctl status neo4j
   ps aux | grep python | grep clustering
   
   # Check logs for errors
   tail -50 /var/log/clustering/*.log | grep -E "(ERROR|CRITICAL|FATAL)"
   ```

2. **Database Recovery**:
   ```bash
   # Restart Neo4j if needed
   sudo systemctl restart neo4j
   
   # Check database integrity
   echo "SHOW DATABASE YIELD name, currentStatus;" | cypher-shell
   ```

3. **Service Restart**:
   ```bash
   # Restart clustering service
   sudo systemctl restart clustering-service  # If using systemd
   
   # Or restart manually
   pkill -f semantic_clustering
   python3 main.py &
   ```

### Rollback Procedures

If clustering system needs to be disabled:

1. **See clustering_rollback_plan.md** for complete rollback procedures
2. **Emergency cluster disable**:
   ```python
   # Disable clustering in pipeline
   # In unified_pipeline.py, comment out:
   # clustering_result = self.clustering_system.run_clustering()
   ```

## Performance Tuning

### Parameter Optimization

**For different data characteristics:**

```yaml
# High-quality, focused content (low diversity)
clustering:
  min_cluster_size_formula: "sqrt_small"
  epsilon: 0.2
  min_samples: 2

# Diverse, varied content (high diversity)
clustering:
  min_cluster_size_formula: "sqrt"
  epsilon: 0.4
  min_samples: 4

# Technical/specialized content
clustering:
  min_cluster_size_formula: "fixed"
  min_cluster_size_fixed: 5
  epsilon: 0.3
```

### Hardware Optimization

**Recommended system specs:**
- **CPU**: 4+ cores for parallel processing
- **RAM**: 8GB minimum, 16GB recommended
- **Storage**: SSD for Neo4j database
- **Network**: Stable connection for LLM API calls

**Neo4j Memory Configuration:**
```bash
# In neo4j.conf
dbms.memory.heap.initial_size=4G
dbms.memory.heap.max_size=8G
dbms.memory.pagecache.size=4G
dbms.transaction.timeout=60s
```

## Backup and Recovery

### Database Backup

```bash
# Create automated backup script
cat > backup_clustering_db.sh << 'EOF'
#!/bin/bash

BACKUP_DIR="/backup/clustering"
DATE=$(date +%Y%m%d_%H%M%S)
DB_NAME="neo4j"

# Create backup directory
mkdir -p "$BACKUP_DIR"

# Stop Neo4j for consistent backup
sudo systemctl stop neo4j

# Create backup
neo4j-admin dump --database="$DB_NAME" --to="$BACKUP_DIR/neo4j_backup_$DATE.dump"

# Start Neo4j
sudo systemctl start neo4j

# Clean old backups (keep last 7 days)
find "$BACKUP_DIR" -name "*.dump" -mtime +7 -delete

echo "Backup completed: neo4j_backup_$DATE.dump"
EOF

chmod +x backup_clustering_db.sh

# Add to crontab for daily backups:
# 0 2 * * * /path/to/backup_clustering_db.sh
```

### Configuration Backup

```bash
# Backup configuration files
tar -czf clustering_config_backup_$(date +%Y%m%d).tar.gz \
  clustering_config.yaml \
  docs/clustering_*.md \
  src/clustering/
```

### Recovery Procedures

```bash
# Restore from backup
sudo systemctl stop neo4j

# Restore database
neo4j-admin load --from="/backup/clustering/neo4j_backup_YYYYMMDD_HHMMSS.dump" \
                 --database="neo4j" --force

sudo systemctl start neo4j
```

---

## Contact Information

For clustering system support:
- **System Administrator**: [admin@company.com]
- **Development Team**: [dev-team@company.com]
- **Emergency Contact**: [emergency@company.com]

## Version History

- **v1.0**: Initial maintenance guide
- **Current**: Phase 7 production release

---

*This maintenance guide should be reviewed and updated quarterly to ensure accuracy and completeness.*