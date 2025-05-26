# Deployment Guide

This guide covers various deployment strategies for the Podcast Knowledge Graph Pipeline, from development environments to production deployments.

## Table of Contents

1. [Deployment Options](#deployment-options)
2. [Local Development](#local-development)
3. [Docker Deployment](#docker-deployment)
4. [Kubernetes Deployment](#kubernetes-deployment)
5. [Cloud Deployments](#cloud-deployments)
6. [Production Considerations](#production-considerations)
7. [Monitoring and Observability](#monitoring-and-observability)
8. [Scaling Strategies](#scaling-strategies)
9. [Disaster Recovery](#disaster-recovery)

## Deployment Options

### Overview of Deployment Strategies

| Strategy | Use Case | Pros | Cons |
|----------|----------|------|------|
| Local | Development/Testing | Simple setup, full control | Not scalable, resource limited |
| Docker | Single server deployment | Portable, consistent environment | Limited scaling |
| Kubernetes | Production, multi-server | Highly scalable, self-healing | Complex setup |
| Serverless | Batch processing | Cost-effective, auto-scaling | Cold starts, time limits |
| Managed Services | Enterprise | Minimal maintenance | Vendor lock-in, cost |

## Local Development

### Quick Start

```bash
# Clone repository
git clone https://github.com/your-org/podcast_kg_pipeline.git
cd podcast_kg_pipeline

# Setup Python environment
python -m venv venv
source venv/bin/activate  # On Windows: venv\Scripts\activate

# Install dependencies
pip install -r requirements.txt
pip install -e .

# Setup configuration
cp .env.example .env
cp config/config.example.yml config/config.dev.yml
# Edit both files with your settings

# Start dependencies (Neo4j)
docker-compose up -d neo4j

# Run the pipeline
python -m podcast_kg_pipeline.cli seed-podcast \
    --config config/config.dev.yml \
    --podcast-url "https://example.com/podcast.rss"
```

### Development Environment

```yaml
# docker-compose.yml for development
version: '3.8'

services:
  neo4j:
    image: neo4j:5.12.0
    ports:
      - "7474:7474"
      - "7687:7687"
    environment:
      - NEO4J_AUTH=neo4j/password
      - NEO4J_PLUGINS=["apoc", "graph-data-science"]
    volumes:
      - neo4j_data:/data
      - neo4j_logs:/logs

  redis:
    image: redis:7-alpine
    ports:
      - "6379:6379"
    volumes:
      - redis_data:/data

volumes:
  neo4j_data:
  neo4j_logs:
  redis_data:
```

## Docker Deployment

### Single Container Deployment

```dockerfile
# Dockerfile
FROM python:3.10-slim

# Install system dependencies
RUN apt-get update && apt-get install -y \
    ffmpeg \
    git \
    && rm -rf /var/lib/apt/lists/*

# Create app directory
WORKDIR /app

# Install Python dependencies
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# Copy application code
COPY . .
RUN pip install -e .

# Create non-root user
RUN useradd -m -u 1000 podcast && chown -R podcast:podcast /app
USER podcast

# Set environment variables
ENV PYTHONUNBUFFERED=1
ENV PODCAST_KG_LOG_LEVEL=INFO

# Run the application
CMD ["python", "-m", "podcast_kg_pipeline.cli"]
```

### Docker Compose Production

```yaml
# docker-compose.prod.yml
version: '3.8'

services:
  app:
    build: .
    environment:
      - NEO4J_URI=bolt://neo4j:7687
      - REDIS_URL=redis://redis:6379
    volumes:
      - ./config:/app/config:ro
      - ./data:/app/data
    depends_on:
      - neo4j
      - redis
    restart: unless-stopped
    deploy:
      resources:
        limits:
          cpus: '4'
          memory: 8G
        reservations:
          cpus: '2'
          memory: 4G

  neo4j:
    image: neo4j:5.12.0-enterprise
    environment:
      - NEO4J_AUTH=neo4j/${NEO4J_PASSWORD}
      - NEO4J_ACCEPT_LICENSE_AGREEMENT=yes
      - NEO4J_dbms_memory_heap_max__size=4G
      - NEO4J_dbms_memory_pagecache_size=2G
    volumes:
      - neo4j_data:/data
      - neo4j_logs:/logs
    ports:
      - "7474:7474"
      - "7687:7687"
    restart: unless-stopped

  redis:
    image: redis:7-alpine
    command: redis-server --appendonly yes
    volumes:
      - redis_data:/data
    restart: unless-stopped

  nginx:
    image: nginx:alpine
    volumes:
      - ./nginx.conf:/etc/nginx/nginx.conf:ro
    ports:
      - "80:80"
      - "443:443"
    depends_on:
      - app
    restart: unless-stopped

volumes:
  neo4j_data:
  neo4j_logs:
  redis_data:
```

### Building and Running

```bash
# Build the image
docker build -t podcast-kg-pipeline:latest .

# Run with docker-compose
docker-compose -f docker-compose.prod.yml up -d

# View logs
docker-compose -f docker-compose.prod.yml logs -f app

# Scale workers
docker-compose -f docker-compose.prod.yml up -d --scale app=3
```

## Kubernetes Deployment

### Kubernetes Manifests

```yaml
# k8s/namespace.yaml
apiVersion: v1
kind: Namespace
metadata:
  name: podcast-kg

---
# k8s/configmap.yaml
apiVersion: v1
kind: ConfigMap
metadata:
  name: podcast-kg-config
  namespace: podcast-kg
data:
  config.yml: |
    pipeline:
      batch_size: 10
      max_workers: 4
    providers:
      audio:
        type: whisper
        config:
          model_size: large-v3

---
# k8s/secret.yaml
apiVersion: v1
kind: Secret
metadata:
  name: podcast-kg-secrets
  namespace: podcast-kg
type: Opaque
stringData:
  NEO4J_PASSWORD: "your-password"
  GOOGLE_API_KEY: "your-api-key"

---
# k8s/deployment.yaml
apiVersion: apps/v1
kind: Deployment
metadata:
  name: podcast-kg-pipeline
  namespace: podcast-kg
spec:
  replicas: 3
  selector:
    matchLabels:
      app: podcast-kg-pipeline
  template:
    metadata:
      labels:
        app: podcast-kg-pipeline
    spec:
      containers:
      - name: pipeline
        image: your-registry/podcast-kg-pipeline:latest
        resources:
          requests:
            memory: "4Gi"
            cpu: "2"
          limits:
            memory: "8Gi"
            cpu: "4"
        env:
        - name: NEO4J_URI
          value: "bolt://neo4j-service:7687"
        - name: NEO4J_PASSWORD
          valueFrom:
            secretKeyRef:
              name: podcast-kg-secrets
              key: NEO4J_PASSWORD
        volumeMounts:
        - name: config
          mountPath: /app/config
          readOnly: true
        - name: data
          mountPath: /app/data
      volumes:
      - name: config
        configMap:
          name: podcast-kg-config
      - name: data
        persistentVolumeClaim:
          claimName: podcast-kg-data

---
# k8s/pvc.yaml
apiVersion: v1
kind: PersistentVolumeClaim
metadata:
  name: podcast-kg-data
  namespace: podcast-kg
spec:
  accessModes:
    - ReadWriteMany
  resources:
    requests:
      storage: 100Gi
  storageClassName: fast-ssd

---
# k8s/job.yaml
apiVersion: batch/v1
kind: Job
metadata:
  name: podcast-seeding-job
  namespace: podcast-kg
spec:
  template:
    spec:
      containers:
      - name: seeder
        image: your-registry/podcast-kg-pipeline:latest
        command: ["python", "-m", "podcast_kg_pipeline.cli", "seed-podcasts", "--config", "/app/config/config.yml"]
        env:
        - name: NEO4J_URI
          value: "bolt://neo4j-service:7687"
        envFrom:
        - secretRef:
            name: podcast-kg-secrets
      restartPolicy: OnFailure
  backoffLimit: 3
```

### Helm Chart

```yaml
# helm/values.yaml
replicaCount: 3

image:
  repository: your-registry/podcast-kg-pipeline
  tag: latest
  pullPolicy: IfNotPresent

resources:
  limits:
    cpu: 4
    memory: 8Gi
  requests:
    cpu: 2
    memory: 4Gi

neo4j:
  enabled: true
  auth:
    password: changeme
  persistence:
    enabled: true
    size: 100Gi

redis:
  enabled: true
  auth:
    enabled: true
    password: changeme

autoscaling:
  enabled: true
  minReplicas: 2
  maxReplicas: 10
  targetCPUUtilizationPercentage: 70
  targetMemoryUtilizationPercentage: 80

monitoring:
  prometheus:
    enabled: true
  grafana:
    enabled: true
```

### Deployment Commands

```bash
# Deploy with kubectl
kubectl apply -f k8s/

# Deploy with Helm
helm install podcast-kg ./helm -n podcast-kg --create-namespace

# Check deployment status
kubectl get pods -n podcast-kg
kubectl logs -f deployment/podcast-kg-pipeline -n podcast-kg

# Scale deployment
kubectl scale deployment podcast-kg-pipeline --replicas=5 -n podcast-kg
```

## Cloud Deployments

### AWS Deployment

```bash
# Using AWS ECS with Fargate
aws ecs create-cluster --cluster-name podcast-kg-cluster

# Create task definition
aws ecs register-task-definition --cli-input-json file://ecs-task-definition.json

# Create service
aws ecs create-service \
    --cluster podcast-kg-cluster \
    --service-name podcast-kg-service \
    --task-definition podcast-kg-task:1 \
    --desired-count 3 \
    --launch-type FARGATE
```

### Google Cloud Platform

```bash
# Using Google Cloud Run
gcloud run deploy podcast-kg-pipeline \
    --image gcr.io/your-project/podcast-kg-pipeline \
    --platform managed \
    --region us-central1 \
    --memory 8Gi \
    --cpu 4 \
    --timeout 3600 \
    --max-instances 10 \
    --set-env-vars NEO4J_URI=bolt://neo4j-host:7687
```

### Azure Container Instances

```bash
# Deploy to Azure
az container create \
    --resource-group podcast-kg-rg \
    --name podcast-kg-pipeline \
    --image yourregistry.azurecr.io/podcast-kg-pipeline:latest \
    --cpu 4 \
    --memory 8 \
    --environment-variables NEO4J_URI=bolt://neo4j:7687
```

## Production Considerations

### Security

1. **Secrets Management**:
   ```bash
   # Use cloud provider secret managers
   aws secretsmanager create-secret --name podcast-kg/api-keys
   gcloud secrets create api-keys --data-file=secrets.json
   az keyvault secret set --vault-name podcast-kg --name api-keys
   ```

2. **Network Security**:
   - Use VPC/VNet for internal communication
   - Implement firewall rules
   - Use SSL/TLS for all connections
   - Rotate credentials regularly

3. **Access Control**:
   - Implement RBAC for Kubernetes
   - Use IAM roles for cloud services
   - Audit access logs

### Performance Optimization

1. **Resource Allocation**:
   ```yaml
   # Optimize based on workload
   resources:
     requests:
       memory: "4Gi"
       cpu: "2"
       nvidia.com/gpu: 1  # For Whisper GPU acceleration
     limits:
       memory: "8Gi"
       cpu: "4"
       nvidia.com/gpu: 1
   ```

2. **Caching Strategy**:
   - Use Redis for LLM response caching
   - Implement embedding cache
   - Cache processed segments

3. **Database Optimization**:
   ```cypher
   // Create indexes for performance
   CREATE INDEX podcast_name FOR (p:Podcast) ON (p.name);
   CREATE INDEX episode_title FOR (e:Episode) ON (e.title);
   CREATE INDEX entity_name FOR (en:Entity) ON (en.name);
   ```

### High Availability

1. **Multi-Region Deployment**:
   ```yaml
   # Deploy across regions
   regions:
     - us-east-1
     - eu-west-1
     - ap-southeast-1
   ```

2. **Load Balancing**:
   - Use cloud load balancers
   - Implement health checks
   - Configure session affinity if needed

3. **Failover Strategy**:
   - Automated failover for Neo4j
   - Redis sentinel for HA
   - Cross-region replication

## Monitoring and Observability

### Metrics Collection

```yaml
# prometheus-config.yaml
global:
  scrape_interval: 15s

scrape_configs:
  - job_name: 'podcast-kg-pipeline'
    static_configs:
    - targets: ['localhost:8000']
    metrics_path: '/metrics'
```

### Key Metrics to Monitor

1. **Application Metrics**:
   - Episodes processed per hour
   - Average processing time per episode
   - Error rate by provider
   - Queue depth and processing lag

2. **Infrastructure Metrics**:
   - CPU and memory utilization
   - Disk I/O and space
   - Network throughput
   - GPU utilization (for Whisper)

3. **Business Metrics**:
   - Knowledge nodes created
   - Extraction quality scores
   - Provider API usage and costs

### Alerting Rules

```yaml
# alerts.yaml
groups:
  - name: podcast-kg-alerts
    rules:
    - alert: HighErrorRate
      expr: rate(podcast_kg_errors_total[5m]) > 0.1
      for: 10m
      annotations:
        summary: High error rate detected
        
    - alert: ProcessingLag
      expr: podcast_kg_queue_depth > 100
      for: 30m
      annotations:
        summary: Processing queue is backing up
        
    - alert: MemoryPressure
      expr: container_memory_usage_bytes / container_spec_memory_limit_bytes > 0.9
      for: 5m
      annotations:
        summary: Container memory usage is high
```

## Scaling Strategies

### Horizontal Scaling

```yaml
# HPA configuration
apiVersion: autoscaling/v2
kind: HorizontalPodAutoscaler
metadata:
  name: podcast-kg-hpa
spec:
  scaleTargetRef:
    apiVersion: apps/v1
    kind: Deployment
    name: podcast-kg-pipeline
  minReplicas: 2
  maxReplicas: 20
  metrics:
  - type: Resource
    resource:
      name: cpu
      target:
        type: Utilization
        averageUtilization: 70
  - type: Resource
    resource:
      name: memory
      target:
        type: Utilization
        averageUtilization: 80
  - type: Pods
    pods:
      metric:
        name: queue_depth
      target:
        type: AverageValue
        averageValue: "30"
```

### Vertical Scaling

- Monitor resource usage patterns
- Adjust resource requests/limits
- Use node pools with different specs
- Consider GPU nodes for audio processing

### Queue-Based Scaling

```python
# Implement dynamic scaling based on queue depth
import boto3

def scale_workers(queue_depth):
    if queue_depth > 100:
        desired_count = min(20, queue_depth // 10)
    else:
        desired_count = 2
    
    ecs = boto3.client('ecs')
    ecs.update_service(
        cluster='podcast-kg-cluster',
        service='podcast-kg-service',
        desiredCount=desired_count
    )
```

## Disaster Recovery

### Backup Strategy

1. **Database Backups**:
   ```bash
   # Neo4j backup
   neo4j-admin backup --database=neo4j --backup-dir=/backups/
   
   # Automated daily backups
   0 2 * * * /usr/bin/neo4j-admin backup --database=neo4j --backup-dir=/backups/$(date +%Y%m%d)
   ```

2. **Checkpoint Backups**:
   - Store checkpoints in object storage (S3, GCS, Azure Blob)
   - Implement retention policies
   - Test restore procedures

3. **Configuration Backups**:
   - Version control all configurations
   - Use GitOps for deployment configs
   - Document all environment-specific settings

### Recovery Procedures

1. **Database Recovery**:
   ```bash
   # Restore Neo4j
   neo4j-admin restore --from=/backups/20240115 --database=neo4j --force
   ```

2. **Application Recovery**:
   - Use checkpoint recovery to resume processing
   - Validate data integrity after recovery
   - Monitor for any missing data

3. **Disaster Recovery Testing**:
   - Monthly DR drills
   - Document recovery time objectives (RTO)
   - Maintain runbooks for common scenarios

### Business Continuity

1. **Multi-Region Setup**:
   - Active-passive or active-active
   - Data replication across regions
   - Automated failover procedures

2. **Communication Plan**:
   - Incident response team contacts
   - Stakeholder notification procedures
   - Status page for users

3. **Post-Incident Review**:
   - Root cause analysis
   - Process improvements
   - Update documentation

## Conclusion

Successful deployment requires:
- Choosing the right deployment strategy for your needs
- Implementing proper monitoring and alerting
- Planning for scalability from the start
- Having robust disaster recovery procedures
- Regular testing and optimization

Start simple with Docker, then scale to Kubernetes or cloud services as your needs grow. Always prioritize security, monitoring, and data integrity in your deployment strategy.