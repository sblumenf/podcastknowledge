# VTT Pipeline Deployment Guide

This guide provides step-by-step instructions for deploying the VTT Knowledge Pipeline. It is designed to be followed by AI agents or developers with minimal prior knowledge of the system.

## Table of Contents

1. [System Requirements](#system-requirements)
2. [Quick Start](#quick-start)
3. [Detailed Setup](#detailed-setup)
4. [Configuration](#configuration)
5. [Verification](#verification)
6. [Usage](#usage)
7. [Troubleshooting](#troubleshooting)
8. [Resource Optimization](#resource-optimization)

## System Requirements

### Minimal Requirements
- **Operating System**: Linux, macOS, or Windows
- **Python**: 3.11 or higher
- **RAM**: 2GB minimum (4GB recommended)
- **Storage**: 500MB free space
- **Network**: Internet connection for API calls

### Optional Requirements
- **Neo4j**: 4.4+ (for knowledge graph storage)
- **Docker**: 20.10+ (for containerized deployment)

## Quick Start

For the fastest deployment, use the quickstart script:

```bash
# Clone the repository
git clone <repository-url>
cd seeding_pipeline

# Run quickstart
./quickstart.sh  # Linux/Mac
# or
python quickstart.py  # Windows
```

This will set up everything automatically. Skip to [Verification](#verification) after running.

## Detailed Setup

### Step 1: Clone Repository

```bash
git clone <repository-url>
cd seeding_pipeline
```

### Step 2: Create Virtual Environment

**Linux/macOS:**
```bash
python3 -m venv venv
source venv/bin/activate
```

**Windows:**
```cmd
python -m venv venv
venv\Scripts\activate
```

**Verification:**
Your prompt should show `(venv)` prefix when activated.

### Step 3: Install Dependencies

**Minimal Installation (Recommended for low resources):**
```bash
pip install -r requirements-core.txt
```

**Full Installation (If you have 4GB+ RAM):**
```bash
pip install -r requirements.txt
```

**Expected Output:**
```
Successfully installed neo4j-5.14.0 python-dotenv-1.0.0 ...
```

### Step 4: Set Up Configuration

1. Copy the environment template:
   ```bash
   cp .env.template .env
   ```

2. Edit `.env` with your credentials:
   ```bash
   nano .env  # or your preferred editor
   ```

3. Required settings:
   ```ini
   # Neo4j Database (required)
   NEO4J_PASSWORD=your_password_here
   
   # Google API Key (required for LLM processing)
   GOOGLE_API_KEY=your_api_key_here
   ```

### Step 5: Verify Installation

Run the validation script:
```bash
python scripts/validate_deployment.py
```

All critical checks should pass (✓). Warnings (⚠) are acceptable.

## Configuration

### Environment Variables

| Variable | Required | Default | Description |
|----------|----------|---------|-------------|
| `NEO4J_URI` | No | `bolt://localhost:7687` | Neo4j connection URI |
| `NEO4J_USERNAME` | No | `neo4j` | Database username |
| `NEO4J_PASSWORD` | Yes | - | Database password |
| `GOOGLE_API_KEY` | Yes | - | Google Gemini API key |
| `LOG_LEVEL` | No | `INFO` | Logging verbosity |
| `MAX_MEMORY_MB` | No | `2048` | Memory limit |
| `MAX_CONCURRENT_FILES` | No | `1` | Parallel processing limit |

### Low Resource Mode

For systems with <4GB RAM, enable low-resource mode:

```bash
# Set in .env
MAX_MEMORY_MB=1024
MAX_CONCURRENT_FILES=1
ENABLE_ENHANCED_LOGGING=false
ENABLE_METRICS=false

# Or use CLI flag
python -m src.cli.cli --low-resource process-vtt --folder /path/to/vtts
```

## Verification

### 1. Run Smoke Tests

```bash
python scripts/run_minimal_tests.py
```

Expected: All tests pass in <30 seconds.

### 2. Test CLI

```bash
# Check help
python -m src.cli.cli --help

# Use minimal CLI for testing
python src/cli/minimal_cli.py test_vtt/sample.vtt --dry-run
```

### 3. Process Test File

Create `test.vtt`:
```
WEBVTT

00:00:00.000 --> 00:00:05.000
This is a test transcript.
```

Process it:
```bash
python -m src.cli.cli process-vtt --folder . --pattern test.vtt --dry-run
```

## Usage

### Basic VTT Processing

```bash
# Process single file
python src/cli/minimal_cli.py /path/to/file.vtt

# Process folder
python -m src.cli.cli process-vtt --folder /path/to/vtt/files

# Process with pattern
python -m src.cli.cli process-vtt --folder /path --pattern "episode*.vtt"

# Recursive processing
python -m src.cli.cli process-vtt --folder /path --recursive
```

### Checkpoint Management

```bash
# View checkpoint status
python -m src.cli.cli checkpoint-status

# Clean checkpoints
python -m src.cli.cli checkpoint-clean --force
```

### Health Monitoring

```bash
# Check system health
python -m src.cli.cli health

# Check specific component
python -m src.cli.cli health --component neo4j
```

## Troubleshooting

### Common Issues

#### 1. ModuleNotFoundError
**Symptom:** `ModuleNotFoundError: No module named 'neo4j'`

**Solution:**
```bash
# Ensure virtual environment is activated
source venv/bin/activate  # Linux/Mac
# or
venv\Scripts\activate  # Windows

# Reinstall dependencies
pip install -r requirements-core.txt
```

#### 2. Neo4j Connection Failed
**Symptom:** `Neo4j connection failed: Unable to connect`

**Solutions:**
1. Start Neo4j service:
   ```bash
   # Docker
   docker start neo4j
   
   # System service
   sudo systemctl start neo4j
   ```

2. Check credentials in `.env`

3. Verify Neo4j is accessible:
   ```bash
   curl http://localhost:7474
   ```

#### 3. Google API Key Invalid
**Symptom:** `Error: Invalid API key`

**Solution:**
1. Get API key from: https://makersuite.google.com/app/apikey
2. Update `.env` file
3. Ensure no extra spaces or quotes

#### 4. Out of Memory
**Symptom:** `MemoryError` or system becomes unresponsive

**Solutions:**
1. Enable low-resource mode:
   ```bash
   python -m src.cli.cli --low-resource process-vtt --folder /path
   ```

2. Process fewer files at once:
   ```bash
   # Process one file at a time
   MAX_CONCURRENT_FILES=1 python -m src.cli.cli process-vtt --folder /path
   ```

3. Reduce batch size in `.env`:
   ```ini
   BATCH_SIZE=5
   MAX_MEMORY_MB=1024
   ```

### Debug Mode

Enable detailed logging for troubleshooting:

```bash
# Set in .env
LOG_LEVEL=DEBUG
DEBUG_MODE=true

# Or use CLI
python -m src.cli.cli -v process-vtt --folder /path
```

Check logs in:
- `deployment_validation.log`
- `logs/` directory (if configured)

## Resource Optimization

### For Systems with <2GB RAM

1. **Use Minimal CLI:**
   ```bash
   python src/cli/minimal_cli.py file.vtt
   ```

2. **Disable Optional Features:**
   ```ini
   # In .env
   ENABLE_ENHANCED_LOGGING=false
   ENABLE_METRICS=false
   USE_SCHEMALESS_EXTRACTION=false
   ```

3. **Process Files Individually:**
   ```bash
   for file in *.vtt; do
       python src/cli/minimal_cli.py "$file"
       sleep 2  # Give system time to recover
   done
   ```

### Docker Deployment (Optional)

For better resource isolation:

```bash
# Build minimal image
docker build -f Dockerfile.minimal -t vtt-pipeline:minimal .

# Run with memory limit
docker run -m 1g --cpus="1.0" \
  -v $(pwd)/input:/input \
  -v $(pwd)/output:/output \
  vtt-pipeline:minimal
```

### Performance Tips

1. **Close Other Applications**: Free up RAM before processing
2. **Use SSD Storage**: Faster checkpoint operations
3. **Process During Off-Hours**: Reduce system load
4. **Monitor Resources**: Use `htop` or Task Manager
5. **Batch Processing**: Process files in groups of 10-20

## Maintenance

### Regular Tasks

1. **Clean Checkpoints Weekly:**
   ```bash
   python -m src.cli.cli checkpoint-clean --force
   ```

2. **Update Dependencies Monthly:**
   ```bash
   pip install --upgrade -r requirements-core.txt
   ```

3. **Check Health Before Major Processing:**
   ```bash
   python -m src.cli.cli health
   ```

### Backup

Important files to backup:
- `.env` (your configuration)
- `checkpoints/` (processing state)
- `output/` (processed results)

## Support

For issues:
1. Run validation: `python scripts/validate_deployment.py`
2. Check troubleshooting section above
3. Enable debug mode and check logs
4. Create minimal reproducible example

## Quick Reference Card

```bash
# Activate environment
source venv/bin/activate

# Process VTT files
python -m src.cli.cli process-vtt --folder /path/to/vtts

# Low-resource mode
python -m src.cli.cli --low-resource process-vtt --folder /path

# Check status
python -m src.cli.cli checkpoint-status

# Validate deployment
python scripts/validate_deployment.py

# Quick test
python src/cli/minimal_cli.py test.vtt --dry-run
```

---

Last updated: 2025-06-07
Deployment guide version: 1.0