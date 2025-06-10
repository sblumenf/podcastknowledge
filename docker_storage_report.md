# Docker Storage Analysis Report

## Executive Summary

Your Docker system is currently experiencing significant storage inefficiency due to:
- **30 Neo4j containers** (29 duplicates of v5.14.0 + 1 v5.15.0-community)
- **59 Docker volumes** consuming approximately **31.7 GB** of storage
- Only **12 containers actively running**, with 18 stopped/exited containers
- Each Neo4j container using ~122MB with 2 associated volumes of ~541MB each

## Container Analysis

### Total Containers: 32
- **30 Neo4j containers** (all database instances)
- **2 Hello-world containers** (test containers)

### Container Status Breakdown:
- **Running**: 12 containers (11 Neo4j v5.14.0, 1 Neo4j v5.15.0-community)
- **Exited**: 19 containers
- **Created**: 1 container (never started)

### Duplication Issues:
- **29 identical Neo4j v5.14.0 containers** - appears to be duplicates from multiple test runs
- All containers are randomly named (e.g., "kind_clarke", "relaxed_keldysh"), indicating they were created without explicit names
- Each container is mapping to different host ports (32769-32814), suggesting repeated test runs

## Storage Usage

### Images (Total: 1.88 GB)
```
vtt-pipeline:test        412MB
<none> (dangling)        285MB
<none> (dangling)        211MB
hello-world:latest       10.1kB
neo4j:5.15.0-community   492MB
neo4j:5.14.0            492MB
```

### Container Storage:
- Each Neo4j container: ~122MB
- Total container storage: ~3.7GB

### Volume Storage:
- 59 volumes total
- Most volumes: ~541MB each (Neo4j data volumes)
- Total volume storage: ~31.7GB

### Build Cache:
- 2.594MB (minimal impact)

## Purpose Identification

### Neo4j Containers:
All Neo4j containers appear to be:
- **Test/development instances** from your podcast knowledge graph seeding pipeline
- Created automatically during testing without proper cleanup
- Each mapping to different ports to avoid conflicts

### Other Containers:
- **vtt-pipeline:test** - Your VTT transcript processing pipeline test image
- **hello-world** - Docker test containers

## Recommendations

### Immediate Actions (Free up ~35GB):
1. **Stop all unnecessary Neo4j containers**:
   ```bash
   docker stop $(docker ps -q --filter ancestor=neo4j:5.14.0)
   ```

2. **Remove stopped containers**:
   ```bash
   docker container prune -f
   ```

3. **Remove unused volumes** (WARNING: This will delete data):
   ```bash
   docker volume prune -f
   ```

### Long-term Solutions:
1. **Use named containers** in your test scripts:
   ```bash
   docker run --name test-neo4j --rm ...
   ```

2. **Implement cleanup in test scripts**:
   - Add `--rm` flag to auto-remove containers after exit
   - Use docker-compose for better container management

3. **Consider using a single Neo4j instance** for all tests with database separation

4. **Remove dangling images**:
   ```bash
   docker image prune -f
   ```

## Impact Assessment

Current storage waste:
- **~28GB from duplicate Neo4j volumes** (assuming you only need 1-2 instances)
- **~3GB from stopped containers**
- **~496MB from dangling images**

**Total potential savings: ~31.5GB**

## Conclusion

Your system has accumulated significant Docker artifacts from repeated test runs of your podcast knowledge seeding pipeline. The 29 duplicate Neo4j containers with their associated volumes are consuming the majority of storage. Implementing the cleanup recommendations above should free up approximately 31.5GB of disk space.