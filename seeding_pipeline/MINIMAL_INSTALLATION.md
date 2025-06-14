# Minimal Installation Guide

This guide explains how to run the VTT Knowledge Graph Pipeline with minimal dependencies in resource-constrained environments.

## Core Requirements

The absolute minimum dependencies required:

```bash
pip install -r requirements-minimal.txt
```

This installs only:
- **neo4j** (5.14.0) - For graph database connectivity
- **python-dotenv** (1.0.0) - For environment configuration
- **pydantic** (2.5.0) - For data validation
- **PyYAML** (6.0.1) - For configuration files

## Optional Dependencies

The following dependencies are optional and the system will work without them:

### 1. psutil (Resource Monitoring)
- **Without**: Uses mock values for memory/CPU monitoring
- **Install**: `pip install psutil==5.9.6`
- **Benefit**: Real resource usage tracking

### 2. google-generativeai (Embeddings)
- **Without**: Returns zero-valued embeddings
- **Install**: `pip install google-generativeai==0.3.2`
- **Benefit**: Real semantic embeddings from Gemini

### 3. numpy (Mathematical Operations)
- **Without**: Uses pure Python for calculations
- **Install**: `pip install numpy==1.24.3`
- **Benefit**: Faster vector operations

### 4. tqdm (Progress Bars)
- **Without**: No visual progress indicators
- **Install**: `pip install tqdm==4.66.1`
- **Benefit**: Progress bars during processing

## Running with Minimal Dependencies

1. **Install core dependencies**:
   ```bash
   pip install -r requirements-minimal.txt
   ```

2. **Set up environment**:
   ```bash
   # Create .env file with Neo4j credentials
   echo "NEO4J_URI=bolt://localhost:7687" >> .env
   echo "NEO4J_USERNAME=neo4j" >> .env
   echo "NEO4J_PASSWORD=your_password" >> .env
   echo "GEMINI_API_KEY=dummy_key_for_testing" >> .env
   ```

3. **Run the pipeline**:
   ```bash
   python -m src.cli.cli process-vtt --folder /path/to/vtt/files
   ```

## Behavior with Minimal Dependencies

When running with only core dependencies:

1. **Memory Monitoring**: Reports mock values (100MB memory, 10% usage)
2. **Embeddings**: Returns 768-dimensional zero vectors
3. **Similarity**: Uses pure Python cosine similarity
4. **Progress**: No visual progress bars
5. **Processing**: Core functionality remains intact

## Gradual Enhancement

Add dependencies as needed:

```bash
# Add real memory monitoring
pip install psutil

# Add real embeddings (requires API key)
pip install google-generativeai numpy

# Add progress visualization
pip install tqdm
```

## Docker Minimal Image

For containerized deployment:

```dockerfile
FROM python:3.11-slim

WORKDIR /app

# Install only core dependencies
COPY requirements-minimal.txt .
RUN pip install --no-cache-dir -r requirements-minimal.txt

COPY . .

CMD ["python", "-m", "src.cli.cli"]
```

## Troubleshooting

### Import Errors
If you see import errors, check:
1. Python version (requires 3.8+)
2. Core dependencies installed
3. Running from correct directory

### Mock Warnings
You'll see warnings like:
- "psutil not available - memory monitoring disabled"
- "google-generativeai not available - Gemini embeddings disabled"

These are normal and indicate the system is using fallbacks.

### Performance
Without numpy, vector operations will be slower but functional. For production use, consider installing numpy.

## Summary

The minimal installation allows running the pipeline on systems with:
- Limited disk space
- Restricted package installation
- Development/testing environments
- CI/CD pipelines

Core functionality is preserved while optional features gracefully degrade.