# VTT Pipeline Dependencies Guide

## Overview

The VTT Pipeline uses a modular dependency structure to minimize installation time and resource usage. Choose the appropriate requirements file based on your needs.

## Requirements Files

### requirements-core.txt (Recommended)
**Size**: ~50MB | **Install Time**: ~60 seconds

Essential dependencies for basic VTT processing:
- `neo4j` - Graph database connectivity
- `google-generativeai` - LLM integration (Gemini API)
- `python-dotenv` - Environment configuration
- `psutil` - System resource monitoring
- `networkx` - Graph analysis (required by ImportanceScorer)
- `tqdm` - Progress bars
- `PyYAML` - Configuration files

**Use when**: You only need to process VTT files and store results in Neo4j.

### requirements-api.txt
**Size**: ~30MB | **Install Time**: ~30 seconds

API server dependencies (install after requirements-core.txt):
- `fastapi` - REST API framework
- `uvicorn` - ASGI server
- `pydantic` - Data validation
- `httpx` - HTTP client
- `python-multipart` - File uploads

**Use when**: You need the REST API interface.

### requirements.txt
**Size**: ~80MB | **Install Time**: ~90 seconds

Full installation including:
- All core dependencies
- API dependencies
- Additional analysis tools (`scipy`, `numpy`)
- Legacy support (`langchain`, `openai`)

**Use when**: You need all features or are upgrading from older versions.

### requirements-minimal.txt (Legacy)
Similar to requirements-core.txt but includes some unused dependencies. Kept for backward compatibility.

## Installation Examples

### Minimal Installation (Recommended)
```bash
# Activate virtual environment first
source venv/bin/activate  # or venv\Scripts\activate on Windows

# Install core dependencies only
pip install -r requirements-core.txt
```

### API Server Installation
```bash
# Install core first
pip install -r requirements-core.txt

# Then add API dependencies
pip install -r requirements-api.txt
```

### Development Installation
```bash
# Install everything including dev tools
pip install -r requirements.txt
pip install -r requirements-dev.txt
```

## Dependency Notes

### Removed Dependencies
The following were removed from core to reduce size:
- `langchain` - Not used in current codebase
- `openai` - Replaced by Google Gemini
- `scipy` - Only used in one optional module
- `numpy` - Not required for core functionality

### Optional Dependencies
These dependencies enable enhanced features but have **fallback implementations**:

- `numpy==1.24.4` - Numerical operations for embeddings (3-5x performance boost)
- `scipy==1.10.1` - Advanced mathematical functions like cosine distance (2-3x performance boost)
- `networkx==3.1` - Graph analysis algorithms for importance scoring (much more accurate centrality calculations)

**Key Feature**: The pipeline will automatically detect missing dependencies and use pure Python fallbacks, so the application **never crashes** due to missing optional dependencies.

#### Feature Detection
Check which optional features are available:
```python
from src.utils.optional_deps import print_available_features
print_available_features()
```

Example output:
```
VTT Pipeline - Available Features:
========================================
  NetworkX graph analysis: ✓
  NumPy acceleration:      ✗ (pure Python)
  SciPy mathematics:       ✓

To enable all features:
  pip install numpy
```

### Platform Notes
- All dependencies are pure Python or have pre-built wheels
- No compilation required on major platforms
- Works on Python 3.8+

## Troubleshooting

### Import Errors
If you get import errors, you may need additional dependencies:
- `ModuleNotFoundError: networkx` → Install requirements-core.txt
- `ModuleNotFoundError: fastapi` → Install requirements-api.txt
- `ModuleNotFoundError: scipy` → Install requirements.txt (full)

### Memory Issues
For low-memory systems (<2GB):
- Use requirements-core.txt only
- Avoid installing scipy/numpy unless required
- Close other applications during installation

### Network Issues
For slow connections:
- Use `pip install --no-cache-dir` to avoid caching
- Install dependencies one at a time
- Consider using a local package mirror