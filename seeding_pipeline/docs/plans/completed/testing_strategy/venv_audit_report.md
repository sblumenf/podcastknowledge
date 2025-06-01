# Virtual Environment Audit Report

**Generated**: 2025-01-06  
**Purpose**: Assess disk space usage and optimization opportunities for virtual environments

## Current State

### Virtual Environments Found
1. `/home/sergeblumenfeld/podcastknowledge/seeding_pipeline/venv` - **5.7GB**
2. `/home/sergeblumenfeld/podcastknowledge/transcriber/venv` - **177MB**

**Total**: 5.9GB

### Space Usage Analysis - Seeding Pipeline

**Top Space Consumers:**
- NVIDIA GPU libraries: **2.7GB** (from sentence-transformers → torch)
- PyTorch: **1.2GB** (required by sentence-transformers)
- Triton: **545MB** (PyTorch dependency)
- cusparselt: **227MB** (NVIDIA CUDA library)
- transformers: **102MB** (HuggingFace)

**Total installed packages**: 240

### Root Cause
The large size is primarily due to `sentence-transformers==2.2.2` dependency which requires:
- PyTorch with CUDA support
- Full NVIDIA GPU runtime libraries
- Machine learning model libraries

### Optimization Opportunities
1. **CPU-only PyTorch**: Could reduce from 5.7GB to ~2GB
2. **Lighter embeddings library**: Alternative to sentence-transformers
3. **Docker-based embeddings**: Move heavy ML to containers
4. **Package cleanup**: Remove development tools not needed in production

### Recommendations
- For development: Keep current setup (GPU acceleration useful)
- For CI/CD: Create minimal requirements without GPU dependencies
- For production: Use containerized approach to isolate heavy dependencies