# VTT Knowledge Seeding Refactor Implementation Plan

## Executive Summary

This plan transforms the current podcast processing pipeline into a streamlined VTT transcript knowledge seeding tool. The refactored system will accept VTT transcript files as input, extract knowledge using LLMs, and build a Neo4j knowledge graph optimized for RAG applications. The project will remove ~50% of the current codebase (RSS feeds, audio processing, excessive monitoring) while maintaining production quality through comprehensive testing and deployment readiness.

**Key Outcomes:**
- Direct VTT file processing (no RSS/audio handling)
- Lean, focused codebase for knowledge extraction
- Preserved RAG-critical features (embeddings, entity resolution, rich metadata)
- Robust test coverage for reliability
- Deployment-ready architecture

## Phase 1: Analysis and Planning (2 days)

### 1.1 Dependency Analysis
- [x] **Analyze current dependencies**
  - Purpose: Identify what can be removed safely
  - Steps:
    1. Run `pip list` and save current dependencies
    2. Analyze imports in all Python files using AST
    3. Map dependencies to functionality (audio, monitoring, etc.)
    4. Create removal candidates list
  - Validation: Dependency map document created

- [x] **Create feature preservation matrix**
  - Purpose: Ensure critical features aren't accidentally removed
  - Steps:
    1. List all current features/capabilities
    2. Mark as: KEEP, REMOVE, or MODIFY
    3. Document reasoning for each decision
    4. Identify interdependencies
  - Validation: Feature matrix reviewed and complete

### 1.2 Architecture Design
- [x] **Design new entry point architecture**
  - Purpose: Define how VTT files flow through the system
  - Steps:
    1. Create architecture diagram for VTT → Knowledge → Neo4j flow
    2. Define new CLI interface structure
    3. Design configuration schema for VTT processing
    4. Plan batch processing approach
  - Validation: Architecture diagram and interface specs complete

- [x] **Design test strategy**
  - Purpose: Ensure comprehensive test coverage
  - Steps:
    1. Define test categories (unit, integration, e2e)
    2. Create test data requirements (sample VTT files)
    3. Plan mock strategies for external services
    4. Define coverage targets (>80%)
  - Validation: Test strategy document complete

## Phase 2: Core Refactoring (5 days)

### 2.1 Remove Audio/RSS Components
- [ ] **Remove audio providers**
  - Purpose: Eliminate Whisper and audio processing
  - Steps:
    1. Delete `src/providers/audio/` directory
    2. Remove audio provider imports from factories
    3. Update provider factory to exclude audio registration
    4. Remove audio-related configuration options
  - Validation: No audio imports remain, tests pass

- [ ] **Remove RSS feed processing**
  - Purpose: Eliminate podcast feed functionality
  - Steps:
    1. Delete `src/utils/feed_processing.py`
    2. Remove feedparser dependency
    3. Update orchestrator to remove feed-related methods
    4. Clean up feed-related tests
  - Validation: No RSS functionality remains

- [ ] **Clean up audio dependencies**
  - Purpose: Remove ML/audio libraries
  - Steps:
    1. Remove from requirements.txt: torch, whisper, faster-whisper, pyannote
    2. Run `pip uninstall` for each dependency
    3. Verify no import errors
    4. Update setup.py dependencies
  - Validation: Fresh install works without audio deps

### 2.2 Create VTT Processing Components
- [ ] **Implement VTT parser**
  - Purpose: Parse VTT files into expected segment format
  - Steps:
    1. Create `src/processing/vtt_parser.py`
    2. Implement WebVTT parsing with timestamp extraction
    3. Handle speaker notation (<v Speaker>)
    4. Create segment normalization logic
  - Validation: Parses sample VTT files correctly

- [ ] **Create transcript ingestion module**
  - Purpose: Main entry point for VTT processing
  - Steps:
    1. Create `src/seeding/transcript_ingestion.py`
    2. Implement folder scanning for VTT files
    3. Add batch processing logic
    4. Integrate with existing checkpoint system
  - Validation: Successfully processes folder of VTT files

- [ ] **Update pipeline executor**
  - Purpose: Adapt pipeline for transcript-first flow
  - Steps:
    1. Modify `_prepare_segments` to accept VTT segments
    2. Remove audio download steps
    3. Update progress tracking for VTT files
    4. Ensure checkpoint compatibility
  - Validation: Pipeline processes VTT segments end-to-end

### 2.3 Simplify Configuration
- [ ] **Consolidate configuration files**
  - Purpose: Simplify configuration management
  - Steps:
    1. Merge essential configs into single `config.yml`
    2. Remove audio-related configuration options
    3. Add VTT-specific settings (folder paths, parsing options)
    4. Update config validation logic
  - Validation: Single config file handles all settings

- [ ] **Update environment configuration**
  - Purpose: Streamline environment variables
  - Steps:
    1. Remove audio service environment variables
    2. Add VTT processing environment options
    3. Update `.env.example` file
    4. Document all environment variables
  - Validation: Clean environment setup works

## Phase 3: Monitoring and Infrastructure Cleanup (3 days)

### 3.1 Simplify Monitoring
- [ ] **Remove distributed tracing**
  - Purpose: Eliminate Jaeger/OpenTelemetry overhead
  - Steps:
    1. Delete `src/tracing/` directory
    2. Remove OpenTelemetry dependencies
    3. Remove tracing decorators from code
    4. Keep basic logging for debugging
  - Validation: No tracing imports, logging still works

- [ ] **Streamline metrics collection**
  - Purpose: Keep only essential metrics
  - Steps:
    1. Remove Prometheus exporters
    2. Keep internal performance metrics for logging
    3. Remove Grafana dashboards
    4. Update metric collection to use logging
  - Validation: Basic metrics logged, no external systems

- [ ] **Simplify health checks**
  - Purpose: Maintain basic health monitoring
  - Steps:
    1. Create simple health check for Neo4j connection
    2. Remove complex SLO tracking
    3. Keep basic readiness check
    4. Log health status instead of API endpoints
  - Validation: Health checks work without API

### 3.2 Optimize API Layer
- [ ] **Remove unnecessary API endpoints**
  - Purpose: Keep only essential APIs
  - Steps:
    1. Remove podcast seeding endpoints
    2. Keep health check endpoint
    3. Add VTT processing status endpoint
    4. Simplify API structure
  - Validation: Minimal API serves core needs

- [ ] **Create lightweight deployment option**
  - Purpose: Enable easy deployment when needed
  - Steps:
    1. Create simple Dockerfile for VTT processor
    2. Remove Kubernetes manifests
    3. Create docker-compose.yml with just Neo4j and app
    4. Document deployment process
  - Validation: Docker deployment works locally

## Phase 4: CLI and Interface Updates (2 days)

### 4.1 Redesign CLI Interface
- [ ] **Create new CLI structure**
  - Purpose: Focused interface for VTT processing
  - Steps:
    1. Redesign `cli.py` with VTT-focused commands
    2. Add `process-vtt` as main command
    3. Include folder scanning options
    4. Add progress indicators
  - Validation: CLI processes VTT folders successfully

- [ ] **Implement batch processing commands**
  - Purpose: Handle multiple VTT files efficiently
  - Steps:
    1. Add `--folder` option for directory processing
    2. Implement `--pattern` for file filtering (*.vtt)
    3. Add `--recursive` option for nested folders
    4. Create `--dry-run` option for testing
  - Validation: Batch processing works with options

### 4.2 Error Handling and Recovery
- [ ] **Enhance error handling for VTT processing**
  - Purpose: Graceful handling of malformed files
  - Steps:
    1. Add VTT validation before processing
    2. Implement skip-and-continue for bad files
    3. Create detailed error reporting
    4. Log skipped files with reasons
  - Validation: Handles corrupted VTT files gracefully

- [ ] **Update checkpoint system**
  - Purpose: Track VTT file processing progress
  - Steps:
    1. Modify checkpoint to track VTT files instead of episodes
    2. Add file hash for change detection
    3. Implement resume from specific file
    4. Add checkpoint cleanup command
  - Validation: Can resume interrupted batch processing

## Phase 5: Testing Suite Development (3 days)

### 5.1 Unit Tests
- [ ] **Create VTT parser tests**
  - Purpose: Ensure reliable VTT parsing
  - Steps:
    1. Create test VTT files with various formats
    2. Test timestamp parsing accuracy
    3. Test speaker extraction
    4. Test malformed file handling
  - Validation: 100% coverage of VTT parser

- [ ] **Test knowledge extraction pipeline**
  - Purpose: Verify extraction works with VTT segments
  - Steps:
    1. Create mock VTT segments
    2. Test entity extraction
    3. Test relationship discovery
    4. Test metadata preservation
  - Validation: Extraction tests pass with VTT data

### 5.2 Integration Tests
- [ ] **Create end-to-end VTT processing tests**
  - Purpose: Verify complete pipeline flow
  - Steps:
    1. Create sample VTT files with known content
    2. Process through entire pipeline
    3. Verify Neo4j graph structure
    4. Check entity and relationship creation
  - Validation: E2E tests demonstrate full functionality

- [ ] **Test batch processing scenarios**
  - Purpose: Ensure robust batch handling
  - Steps:
    1. Test folder with mixed file types
    2. Test interruption and resume
    3. Test parallel processing
    4. Test memory usage with large batches
  - Validation: Batch processing is reliable

### 5.3 Performance Tests
- [ ] **Create performance benchmarks**
  - Purpose: Establish performance baselines
  - Steps:
    1. Create benchmark VTT files of various sizes
    2. Measure processing time per segment
    3. Test memory usage patterns
    4. Document performance targets
  - Validation: Performance meets targets

## Phase 6: Documentation and Finalization (2 days)

### 6.1 Documentation Updates
- [ ] **Update README for VTT focus**
  - Purpose: Clear project documentation
  - Steps:
    1. Rewrite README with VTT workflow
    2. Remove RSS/audio references
    3. Add VTT format specifications
    4. Include quickstart guide
  - Validation: New users can start quickly

- [ ] **Create migration guide**
  - Purpose: Help users transition from old version
  - Steps:
    1. Document removed features
    2. Explain VTT file requirements
    3. Provide conversion tips
    4. Include troubleshooting section
  - Validation: Migration path is clear

### 6.2 Final Optimization
- [ ] **Code cleanup and optimization**
  - Purpose: Final quality improvements
  - Steps:
    1. Run linting and fix all issues
    2. Remove dead code and unused imports
    3. Optimize critical path performance
    4. Add type hints throughout
  - Validation: Clean code analysis passes

- [ ] **Security audit**
  - Purpose: Ensure security best practices
  - Steps:
    1. Review dependency vulnerabilities
    2. Check for exposed credentials
    3. Validate input sanitization
    4. Update security documentation
  - Validation: Security scan passes

## Success Criteria

### Quantitative Metrics
- **Codebase reduction**: 40-50% fewer lines of code
- **Dependency reduction**: Remove 15+ packages (torch, whisper, etc.)
- **Test coverage**: >80% for core functionality
- **Performance**: Process 100 VTT files in <10 minutes
- **Memory usage**: <2GB for typical workload
- **Setup time**: <5 minutes from clone to first run

### Qualitative Outcomes
- **Focused functionality**: Only VTT → Knowledge → Graph
- **Developer experience**: Clear, simple API and CLI
- **Maintainability**: Reduced complexity, clear architecture
- **Deployment ready**: Docker support, basic monitoring
- **RAG optimized**: All features support future RAG use

### Validation Checklist
- [ ] VTT files process successfully
- [ ] Knowledge extraction produces expected entities
- [ ] Neo4j graph structure is correct
- [ ] Tests provide confidence in changes
- [ ] Documentation is complete and accurate
- [ ] No RSS/audio code remains
- [ ] Deployment works in Docker

## Technology Requirements

### Existing Technologies (No approval needed)
- Python 3.11+
- Neo4j database
- FastAPI (simplified)
- OpenAI/Anthropic APIs
- Docker

### Removed Technologies
- PyTorch
- Whisper/faster-whisper
- Pyannote.audio
- Jaeger/OpenTelemetry
- Prometheus/Grafana
- Kubernetes
- Redis (optional - decision pending)

### New Technologies (Requires approval)
- **webvtt-py**: For robust VTT parsing (lightweight, pure Python)
  - Alternative: Build custom VTT parser
  - Decision needed: Use library or build parser?

## Risk Mitigation

### Technical Risks
1. **VTT format variations**: Mitigate with robust parser and validation
2. **Performance regression**: Mitigate with comprehensive benchmarks
3. **Feature loss**: Mitigate with feature matrix tracking

### Process Risks
1. **Scope creep**: Stick to VTT-only focus
2. **Over-optimization**: Balance cleanup with functionality
3. **Breaking changes**: Version appropriately, document migration

## Implementation Notes

- Each phase builds on the previous one
- Checkpoints after each major phase allow for course correction
- Testing happens continuously, not just in Phase 5
- Documentation updates happen alongside code changes
- Regular commits with clear messages for tracking progress