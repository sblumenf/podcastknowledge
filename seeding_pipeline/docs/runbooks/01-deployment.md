# Runbook: Application Deployment

## Description
Step-by-step guide for deploying the Podcast Knowledge Graph Pipeline to production.

## Prerequisites
- Access to Kubernetes cluster
- `kubectl` configured with proper context
- Docker registry credentials
- Required secrets created in cluster
- Deployment permissions

## Deployment Steps

### 1. Pre-Deployment Checks
```bash
# Verify cluster access
kubectl cluster-info
kubectl get nodes

# Check namespace exists
kubectl get namespace podcast-kg

# Verify secrets are present
kubectl get secrets -n podcast-kg
```

### 2. Update Container Image
```bash
# Set the new version
export VERSION=v1.0.0

# Update deployment image
kubectl set image deployment/podcast-kg-pipeline \
  podcast-kg=your-registry/podcast-kg-pipeline:${VERSION} \
  -n podcast-kg
```

### 3. Apply Configuration Updates
```bash
# Apply any config changes
kubectl apply -f k8s/02-configmap.yaml

# Restart pods to pick up config changes if needed
kubectl rollout restart deployment/podcast-kg-pipeline -n podcast-kg
```

### 4. Monitor Deployment
```bash
# Watch rollout status
kubectl rollout status deployment/podcast-kg-pipeline -n podcast-kg

# Check pod status
kubectl get pods -n podcast-kg -l app=podcast-kg-pipeline

# View deployment events
kubectl describe deployment podcast-kg-pipeline -n podcast-kg
```

### 5. Verify Health
```bash
# Check pod logs
kubectl logs -f deployment/podcast-kg-pipeline -n podcast-kg --tail=50

# Test health endpoint
kubectl port-forward service/podcast-kg-api 8000:8000 -n podcast-kg
curl http://localhost:8000/health

# Check metrics
curl http://localhost:8000/metrics
```

## Rollback Procedure

If deployment fails:

```bash
# Rollback to previous version
kubectl rollout undo deployment/podcast-kg-pipeline -n podcast-kg

# Check rollback status
kubectl rollout status deployment/podcast-kg-pipeline -n podcast-kg

# Verify pods are healthy
kubectl get pods -n podcast-kg
```

## Post-Deployment

### Smoke Tests
```bash
# Test basic functionality
python scripts/smoke_test.py --endpoint https://api.podcast-kg.example.com

# Process a test podcast
kubectl exec -it deployment/podcast-kg-pipeline -n podcast-kg -- \
  python -m cli seed-podcast --url "https://example.com/test.rss" --max-episodes 1
```

### Update Documentation
- [ ] Update deployment log
- [ ] Note any issues encountered
- [ ] Update version in documentation

## Troubleshooting

### Pods Not Starting
```bash
# Check pod events
kubectl describe pod <pod-name> -n podcast-kg

# Check resource availability
kubectl top nodes
kubectl describe node <node-name>
```

### Image Pull Errors
```bash
# Check image exists
docker pull your-registry/podcast-kg-pipeline:${VERSION}

# Verify registry credentials
kubectl get secret regcred -n podcast-kg -o yaml
```

### Configuration Issues
```bash
# Validate ConfigMap
kubectl get configmap podcast-kg-config -n podcast-kg -o yaml

# Check environment variables
kubectl exec -it <pod-name> -n podcast-kg -- env | grep PODCAST
```

## Related Runbooks
- [02-startup-shutdown.md](02-startup-shutdown.md)
- [04-update-rollback.md](04-update-rollback.md)
- [11-health-checks.md](11-health-checks.md)