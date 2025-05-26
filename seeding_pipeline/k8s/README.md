# Kubernetes Deployment for Podcast Knowledge Graph Pipeline

This directory contains Kubernetes manifests for deploying the Podcast Knowledge Graph Pipeline.

## Prerequisites

- Kubernetes cluster (1.21+)
- kubectl configured
- Container registry access
- Storage classes: `fast-ssd` and `standard`
- Ingress controller (nginx-ingress recommended)
- cert-manager (for TLS certificates)

## Quick Start

1. **Create namespace and secrets:**
   ```bash
   kubectl create namespace podcast-kg
   
   kubectl create secret generic podcast-kg-secrets \
     --from-literal=NEO4J_PASSWORD=your-secure-password \
     --from-literal=GOOGLE_API_KEY=your-api-key \
     --from-literal=REDIS_PASSWORD=your-redis-password \
     -n podcast-kg
   ```

2. **Deploy using kubectl:**
   ```bash
   kubectl apply -f . -n podcast-kg
   ```

3. **Or deploy using Kustomize:**
   ```bash
   kubectl apply -k .
   ```

## Components

### Core Services
- **Neo4j**: Graph database (StatefulSet)
- **Redis**: Caching layer (Deployment)
- **Application**: Main pipeline (Deployment with HPA)

### Storage
- **PersistentVolumeClaims**: For data, logs, and cache
- **StorageClasses**: Uses `fast-ssd` for performance, `standard` for logs

### Networking
- **Services**: ClusterIP for internal communication
- **Ingress**: External HTTPS access
- **NetworkPolicies**: Secure pod-to-pod communication

### Workloads
- **Deployment**: Main application (3 replicas)
- **Job**: One-time podcast seeding
- **CronJob**: Scheduled updates

### Scaling
- **HorizontalPodAutoscaler**: Auto-scales 2-10 pods based on CPU/memory

## Configuration

### Environment Variables
Edit the ConfigMap in `02-configmap.yaml` or use Kustomize patches.

### Secrets
Never commit real secrets! Use:
- kubectl create secret
- Sealed Secrets
- External Secrets Operator
- HashiCorp Vault

### Resource Limits
Adjust in `07-deployment.yaml`:
```yaml
resources:
  requests:
    memory: "4Gi"
    cpu: "2"
  limits:
    memory: "8Gi"
    cpu: "4"
```

### GPU Support
Uncomment GPU sections in deployment if using Whisper with GPU:
```yaml
resources:
  requests:
    nvidia.com/gpu: 1
  limits:
    nvidia.com/gpu: 1
```

## Operations

### Check Status
```bash
kubectl get all -n podcast-kg
kubectl get pvc -n podcast-kg
kubectl describe pod -l app=podcast-kg-pipeline -n podcast-kg
```

### View Logs
```bash
kubectl logs -f deployment/podcast-kg-pipeline -n podcast-kg
kubectl logs -f job/podcast-seeding-job -n podcast-kg
```

### Scale Application
```bash
kubectl scale deployment podcast-kg-pipeline --replicas=5 -n podcast-kg
```

### Run a One-Time Job
```bash
kubectl create job --from=cronjob/podcast-update-cronjob manual-update -n podcast-kg
```

### Access Services
```bash
# Port-forward Neo4j
kubectl port-forward service/neo4j 7474:7474 7687:7687 -n podcast-kg

# Port-forward Redis
kubectl port-forward service/redis 6379:6379 -n podcast-kg

# Port-forward Application
kubectl port-forward service/podcast-kg-api 8000:8000 -n podcast-kg
```

## Monitoring

### Prometheus Metrics
The application exposes metrics on port 9090 at `/metrics`.

### Health Checks
- Liveness: `/health`
- Readiness: `/ready`

### Dashboards
Import Grafana dashboards from `monitoring/` directory.

## Troubleshooting

### Pod Not Starting
```bash
kubectl describe pod <pod-name> -n podcast-kg
kubectl logs <pod-name> -n podcast-kg --previous
```

### Storage Issues
```bash
kubectl get pvc -n podcast-kg
kubectl describe pvc <pvc-name> -n podcast-kg
```

### Network Issues
```bash
kubectl exec -it <pod-name> -n podcast-kg -- nc -zv neo4j 7687
kubectl exec -it <pod-name> -n podcast-kg -- nc -zv redis 6379
```

### Performance Issues
```bash
kubectl top pods -n podcast-kg
kubectl top nodes
```

## Production Considerations

1. **High Availability**:
   - Deploy across multiple availability zones
   - Use pod anti-affinity rules
   - Configure pod disruption budgets

2. **Security**:
   - Enable RBAC
   - Use network policies
   - Scan images for vulnerabilities
   - Rotate secrets regularly

3. **Backup**:
   - Regular Neo4j backups
   - Persistent volume snapshots
   - Export critical data

4. **Monitoring**:
   - Set up Prometheus/Grafana
   - Configure alerting rules
   - Enable distributed tracing

5. **Cost Optimization**:
   - Use appropriate instance types
   - Enable cluster autoscaling
   - Schedule non-critical jobs during off-peak

## Cleanup

To remove all resources:
```bash
kubectl delete namespace podcast-kg
```

Note: This will delete all data! Backup first if needed.