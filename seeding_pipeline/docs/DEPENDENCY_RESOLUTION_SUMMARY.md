# Dependency Resolution Summary

## Overview

This document summarizes all dependency resolutions implemented to support resource-constrained environments.

## Dependencies Made Optional

### 1. psutil (System Monitoring)
- **Purpose**: Memory and CPU monitoring
- **Resolution**: Created `src/utils/optional_dependencies.py`
- **Fallback**: Mock values (100MB memory, 10% CPU)
- **Impact**: Monitoring features show placeholder values

### 2. google-generativeai (Embeddings)
- **Purpose**: Generate semantic embeddings via Gemini API
- **Resolution**: Created `src/utils/optional_google.py`
- **Fallback**: 768-dimensional zero vectors
- **Impact**: Embeddings non-functional but system runs

### 3. numpy (Numerical Operations)
- **Purpose**: Efficient vector operations
- **Resolution**: Pure Python implementations in `embeddings_gemini.py`
- **Fallback**: Python loops for cosine similarity
- **Impact**: Slower but functional calculations

## Core Dependencies (Required)

These dependencies remain required as they are essential:

1. **neo4j** (5.14.0) - Graph database connectivity
2. **python-dotenv** (1.0.0) - Environment configuration
3. **pydantic** (2.5.0) - Data validation and models
4. **PyYAML** (6.0.1) - Configuration file parsing

## Files Created/Modified

### New Files
1. `src/utils/optional_dependencies.py` - psutil mock wrapper
2. `src/utils/optional_google.py` - google-generativeai mock wrapper
3. `requirements-minimal.txt` - Minimal dependency list
4. `MINIMAL_INSTALLATION.md` - Installation guide
5. `test_minimal_setup.py` - Verification script

### Modified Files
1. `src/services/performance_optimizer.py` - Uses optional psutil
2. `src/utils/metrics.py` - Uses optional psutil
3. `src/services/embeddings_gemini.py` - Uses optional google/numpy
4. `src/services/conversation_analyzer.py` - Fixed missing imports
5. Multiple other files updated to use optional wrappers

## Running with Minimal Dependencies

```bash
# Install only core dependencies
pip install -r requirements-minimal.txt

# Test the setup
python test_minimal_setup.py

# Run the pipeline
python -m src.cli.cli process-vtt --folder /path/to/vtt
```

## Warnings When Running Minimal

Expected warnings (not errors):
- "psutil not available - memory monitoring disabled"
- "google-generativeai not available - Gemini embeddings disabled"
- "numpy not available - using pure Python for similarity calculations"

## Benefits

1. **Reduced Install Size**: From ~500MB to ~50MB
2. **Faster Installation**: From 5+ minutes to <1 minute
3. **Broader Compatibility**: Works on more systems
4. **Development Friendly**: Can test without API keys
5. **CI/CD Ready**: Minimal dependencies for pipelines

## Limitations with Minimal Setup

1. **No Real Embeddings**: Knowledge extraction quality reduced
2. **No Memory Monitoring**: Can't track actual resource usage
3. **Slower Calculations**: Pure Python is slower than numpy
4. **No Progress Bars**: If tqdm not installed

## Gradual Enhancement Path

Start minimal, add as needed:

```bash
# Start with minimal
pip install -r requirements-minimal.txt

# Add monitoring
pip install psutil

# Add embeddings (need API key)
pip install google-generativeai numpy

# Add progress bars
pip install tqdm

# Full installation
pip install -r requirements.txt
```

## Docker Support

Minimal Dockerfile example:

```dockerfile
FROM python:3.11-slim
WORKDIR /app
COPY requirements-minimal.txt .
RUN pip install --no-cache-dir -r requirements-minimal.txt
COPY . .
CMD ["python", "-m", "src.cli.cli"]
```

## Testing

Run the test script to verify minimal setup:

```bash
python test_minimal_setup.py
```

This will verify:
- All mocks work correctly
- Core imports succeed
- Basic functionality operates

---

*Last Updated: 2025-01-13*