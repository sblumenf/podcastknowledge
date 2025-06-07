# VTT Pipeline Deployment Ready Plan

**Purpose**: Transform the VTT pipeline into a deployable application that can process VTT files with minimal resource usage  
**Scope**: Complete deployment solution from dependency management to production-ready execution  
**Target Environment**: Local PC with proper Python environment support

## Executive Summary

This plan transforms the currently non-functional VTT pipeline into a fully deployable application. It addresses all issues identified in the review: missing dependencies, import problems, and lack of proper deployment structure. The result will be a resource-efficient pipeline that can process VTT podcast transcripts into Neo4j knowledge graphs, suitable for deployment and maintenance by AI agents.

## Phase 1: Virtual Environment Setup

### 1.1 Create Virtual Environment Structure
- [x] **Task**: Set up isolated Python virtual environment
  - **Purpose**: Isolate dependencies and ensure clean Python environment
  - **Steps**:
    1. Use context7 MCP tool to review Python virtual environment documentation
    2. Create setup script: `scripts/setup_venv.sh`
    3. Add commands:
       ```bash
       #!/bin/bash
       python3 -m venv venv
       source venv/bin/activate
       pip install --upgrade pip
       ```
    4. Add venv activation instructions to README
    5. Update .gitignore to exclude venv/
  - **Validation**: Script creates and activates virtual environment successfully

### 1.2 Optimize Dependencies
- [x] **Task**: Create minimal dependency files
  - **Purpose**: Reduce resource usage and installation time
  - **Steps**:
    1. Use context7 MCP tool for dependency management best practices
    2. Analyze current requirements files for redundancies
    3. Create `requirements-core.txt` with only essential packages:
       - neo4j==5.14.0
       - python-dotenv==1.0.0
       - google-generativeai==0.3.2
       - psutil==5.9.6
       - networkx==3.1
       - tqdm==4.66.1
       - PyYAML==6.0.1
    4. Create `requirements-api.txt` for optional API functionality
    5. Document which file to use for different deployment scenarios
  - **Validation**: Dependencies install in <60 seconds on modest hardware

### 1.3 Create Installation Script
- [x] **Task**: Automated dependency installation
  - **Purpose**: Enable one-command setup for AI agents
  - **Steps**:
    1. Use context7 MCP tool for installation script patterns
    2. Create `scripts/install.sh`:
       ```bash
       #!/bin/bash
       source venv/bin/activate || exit 1
       pip install -r requirements-core.txt
       echo "Core dependencies installed successfully"
       ```
    3. Add error handling and progress indicators
    4. Create Windows equivalent: `scripts/install.bat`
  - **Validation**: Fresh install completes without errors

## Phase 2: Docker Containerization (Optional)

### 2.1 Create Minimal Dockerfile
- [ ] **Task**: Build lightweight Docker image
  - **Purpose**: Provide containerized deployment option
  - **Steps**:
    1. Use context7 MCP tool for Docker best practices
    2. Create `Dockerfile.minimal`:
       ```dockerfile
       FROM python:3.11-slim
       WORKDIR /app
       COPY requirements-core.txt .
       RUN pip install --no-cache-dir -r requirements-core.txt
       COPY src/ ./src/
       COPY scripts/ ./scripts/
       CMD ["python", "-m", "src.cli.cli"]
       ```
    3. Create `.dockerignore` to exclude unnecessary files
    4. Add docker-compose.yml for complete stack (Neo4j included)
  - **Validation**: Docker image <300MB, builds in <2 minutes

### 2.2 Resource-Limited Docker Configuration
- [ ] **Task**: Configure Docker for minimal resource usage
  - **Purpose**: Run on resource-constrained systems
  - **Steps**:
    1. Use context7 MCP tool for Docker resource limits
    2. Update docker-compose.yml with limits:
       ```yaml
       services:
         vtt-pipeline:
           mem_limit: 1g
           cpus: '1.0'
       ```
    3. Configure Neo4j with minimal heap size
    4. Add volume mounts for persistent data
  - **Validation**: Runs with <2GB total memory usage

## Phase 3: Fix Remaining Code Issues

### 3.1 Remove Heavy Dependencies
- [ ] **Task**: Eliminate resource-intensive imports
  - **Purpose**: Reduce memory footprint and startup time
  - **Steps**:
    1. Use context7 MCP tool for code optimization patterns
    2. Make networkx import optional in ImportanceScorer
    3. Add fallback for when networkx unavailable
    4. Lazy-load heavy modules only when needed
    5. Document which features require which dependencies
  - **Validation**: Basic pipeline runs without networkx

### 3.2 Create Minimal Entry Point
- [ ] **Task**: Simplified CLI for core functionality
  - **Purpose**: Quick testing and minimal resource usage
  - **Steps**:
    1. Use context7 MCP tool for CLI design patterns
    2. Create `src/cli/minimal_cli.py`:
       ```python
       import argparse
       from pathlib import Path
       
       def process_vtt(file_path):
           # Minimal VTT processing
           pass
       
       if __name__ == "__main__":
           parser = argparse.ArgumentParser()
           parser.add_argument("vtt_file", help="Path to VTT file")
           args = parser.parse_args()
           process_vtt(args.vtt_file)
       ```
    3. Add only essential functionality
    4. Create alias in main CLI for backward compatibility
  - **Validation**: Can process test VTT file with minimal imports

## Phase 4: Configuration Management

### 4.1 Environment Configuration
- [ ] **Task**: Simple environment-based configuration
  - **Purpose**: Easy deployment across environments
  - **Steps**:
    1. Use context7 MCP tool for configuration best practices
    2. Create `.env.template` with all required variables:
       ```
       NEO4J_URI=bolt://localhost:7687
       NEO4J_USER=neo4j
       NEO4J_PASSWORD=
       GOOGLE_API_KEY=
       LOG_LEVEL=INFO
       ```
    3. Update code to use sensible defaults
    4. Add validation script for environment setup
  - **Validation**: Application starts with minimal .env file

### 4.2 Resource Configuration
- [ ] **Task**: Configurable resource limits
  - **Purpose**: Adapt to available system resources
  - **Steps**:
    1. Use context7 MCP tool for resource management patterns
    2. Add configuration options:
       - `MAX_MEMORY_MB`: Memory limit for processing
       - `MAX_CONCURRENT_FILES`: Parallel processing limit
       - `BATCH_SIZE`: Processing batch size
    3. Implement automatic resource detection
    4. Add --low-resource flag to CLI
  - **Validation**: Runs on system with 2GB RAM

## Phase 5: Testing and Validation

### 5.1 Create Minimal Test Suite
- [ ] **Task**: Essential tests only
  - **Purpose**: Verify core functionality without heavy test frameworks
  - **Steps**:
    1. Use context7 MCP tool for minimal testing patterns
    2. Create `tests/test_minimal.py`:
       - Test VTT parsing
       - Test basic extraction
       - Test CLI commands
    3. Use built-in unittest (no pytest dependency)
    4. Add quick smoke test script
  - **Validation**: Tests run in <30 seconds

### 5.2 Create Validation Script
- [ ] **Task**: End-to-end validation
  - **Purpose**: Verify deployment success
  - **Steps**:
    1. Use context7 MCP tool for validation patterns
    2. Create `scripts/validate_deployment.sh`:
       - Check Python version
       - Verify dependencies installed
       - Test database connectivity
       - Process sample VTT file
       - Verify output in Neo4j
    3. Add clear success/failure messages
    4. Generate deployment report
  - **Validation**: Fresh deployment passes all checks

## Phase 6: Documentation and Deployment

### 6.1 Create Deployment Guide
- [ ] **Task**: Step-by-step deployment documentation
  - **Purpose**: Enable AI agents to deploy independently
  - **Steps**:
    1. Use context7 MCP tool for deployment documentation patterns
    2. Create `DEPLOYMENT.md`:
       - System requirements (minimal)
       - Virtual environment setup
       - Dependency installation
       - Configuration steps
       - Verification process
    3. Add troubleshooting section
    4. Include resource optimization tips
  - **Validation**: AI agent can follow guide to successful deployment

### 6.2 Create Quick Start Script
- [ ] **Task**: One-command deployment
  - **Purpose**: Fastest path to working pipeline
  - **Steps**:
    1. Use context7 MCP tool for automation patterns
    2. Create `quickstart.sh`:
       ```bash
       #!/bin/bash
       ./scripts/setup_venv.sh
       ./scripts/install.sh
       cp .env.template .env
       echo "Edit .env with your credentials"
       echo "Then run: source venv/bin/activate && python -m src.cli.cli --help"
       ```
    3. Add platform detection (Linux/Mac/Windows)
    4. Include basic error recovery
  - **Validation**: Fresh clone to working pipeline in <5 minutes

## Success Criteria

1. **Deployment Speed**
   - Fresh deployment completes in <5 minutes
   - All dependencies install without errors
   - Clear instructions for AI agents

2. **Resource Efficiency**
   - Runs with <2GB RAM
   - Minimal CPU usage when idle
   - Docker image <300MB (if used)

3. **Core Functionality**
   - Can parse VTT files
   - Can extract entities and relationships
   - Can store results in Neo4j
   - Can run from CLI

4. **Maintainability**
   - No complex dependency chains
   - Clear error messages
   - Modular architecture
   - AI agent friendly

5. **Testing**
   - Basic tests pass
   - End-to-end validation succeeds
   - Can process sample podcast transcript

## Technology Requirements

**No new technologies required** - This plan uses only:
- Python 3.11+ (already available)
- Virtual environments (built-in)
- Docker (optional, for containerization)
- Existing dependencies from requirements files

## Risk Mitigation

1. **Dependency Conflicts**: Use virtual environment isolation
2. **Resource Constraints**: Implement configurable limits
3. **Missing Credentials**: Provide clear setup instructions
4. **Platform Differences**: Test on Linux/Mac/Windows
5. **AI Agent Confusion**: Over-document every step

## Notes for AI Agent Execution

- Each task includes explicit use of context7 MCP tool
- All scripts include error handling and clear output
- Configuration uses environment variables (no hardcoding)
- Minimal approach prioritizes working code over features
- Focus on core VTT processing functionality first