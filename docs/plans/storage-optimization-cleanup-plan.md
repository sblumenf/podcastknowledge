# Storage Optimization and Cleanup Implementation Plan

## Executive Summary

This plan will reduce the podcast knowledge project from 1.057 GB to approximately 20-40 MB by removing non-essential files, consolidating documentation, and optimizing the structure for AI-maintained development. The project will retain all operational code, tests, and minimal configuration while removing virtual environments, redundant documentation, and accumulated artifacts.

## Phase 1: Critical Storage Recovery (Save ~1 GB)

### Task 1.1: Remove Virtual Environments
- [x] Remove seeding_pipeline virtual environment
  - Purpose: Free 758 MB of storage from Python packages
  - Steps:
    1. Use context7 MCP tool to check Python documentation for Docker best practices
    2. Run: `rm -rf /home/sergeblumenfeld/podcastknowledge/seeding_pipeline/venv`
    3. Run: `rm -rf /home/sergeblumenfeld/podcastknowledge/transcriber/venv`
  - Validation: Verify directories no longer exist with `ls -la`

### Task 1.2: Update .gitignore Files
- [x] Update root .gitignore to prevent future storage bloat
  - Purpose: Ensure removed items stay removed
  - Steps:
    1. Use context7 MCP tool to check gitignore documentation patterns
    2. Edit `/home/sergeblumenfeld/podcastknowledge/.gitignore`
    3. Add patterns: `venv/`, `htmlcov/`, `*.log`, `*.tmp`, `.coverage`, `coverage.xml`, `__pycache__/`
    4. If no root .gitignore exists, create one
  - Validation: Run `git check-ignore venv/` to confirm patterns work

### Task 1.3: Clean Coverage Reports
- [x] Remove HTML coverage directories
  - Purpose: Free 9.1 MB of generated reports
  - Steps:
    1. Run: `rm -rf /home/sergeblumenfeld/podcastknowledge/seeding_pipeline/htmlcov`
    2. Run: `rm -rf /home/sergeblumenfeld/podcastknowledge/transcriber/htmlcov`
    3. Run: `rm -f /home/sergeblumenfeld/podcastknowledge/seeding_pipeline/coverage.xml`
  - Validation: Verify removal with `find . -name "htmlcov" -o -name "coverage.xml"`

## Phase 2: Clean Temporary and Log Files

### Task 2.1: Remove Empty Temporary Files
- [x] Clean checkpoint temporary files
  - Purpose: Remove 42 empty .tmp files cluttering the project
  - Steps:
    1. Run: `rm -f /home/sergeblumenfeld/podcastknowledge/transcriber/data/checkpoints/*.tmp`
    2. Run: `find /home/sergeblumenfeld/podcastknowledge -name "*.tmp" -size 0 -delete`
  - Validation: Verify with `find . -name "*.tmp" | wc -l` shows 0

### Task 2.2: Archive and Remove Large Logs
- [x] Handle oversized log files
  - Purpose: Free 7.7 MB while preserving recent logs
  - Steps:
    1. Use context7 MCP tool to check logging best practices
    2. Archive large logs: `gzip /home/sergeblumenfeld/podcastknowledge/transcriber/logs/podcast_transcriber_*.log`
    3. Remove old error logs: `rm -f /home/sergeblumenfeld/podcastknowledge/transcriber/logs/errors_*.log`
    4. Create .gitkeep in logs directories to maintain structure
  - Validation: Check remaining log size with `du -sh */logs/`

## Phase 3: Consolidate Test Artifacts

### Task 3.1: Clean Benchmark Files
- [x] Reduce benchmark file proliferation
  - Purpose: Keep only latest baseline, remove 30+ timestamped files
  - Steps:
    1. Use context7 MCP tool to review benchmark documentation
    2. Identify latest baseline: `ls -t seeding_pipeline/tests/benchmarks/baseline*.json | head -1`
    3. Keep only: `baseline_metrics.json` and latest `baseline_YYYYMMDD*.json`
    4. Archive others: `mkdir -p archives/benchmarks && mv seeding_pipeline/tests/benchmarks/neo4j_benchmark_*.json archives/benchmarks/`
    5. Remove archives: `rm -rf archives`
  - Validation: Count remaining benchmarks: `ls seeding_pipeline/tests/benchmarks/*.json | wc -l`

### Task 3.2: Remove Test Backups
- [x] Clean test-related archives
  - Purpose: Remove 1.3 MB backup and other test artifacts
  - Steps:
    1. Run: `rm -f /home/sergeblumenfeld/podcastknowledge/seeding_pipeline/tests_backup_*.tar.gz`
    2. Clean test outputs: `rm -rf /home/sergeblumenfeld/podcastknowledge/seeding_pipeline/test_output`
    3. Clean test results: `rm -rf /home/sergeblumenfeld/podcastknowledge/seeding_pipeline/test_results`
  - Validation: Verify with `find . -name "*backup*" -o -name "test_output"`

## Phase 4: Documentation Minimization

### Task 4.1: Create Minimal Documentation Structure
- [x] Reduce documentation to essentials only
  - Purpose: Keep only what's needed for AI-maintained operations
  - Steps:
    1. Use context7 MCP tool to review documentation best practices
    2. Create consolidated structure:
       ```
       docs/
       ├── README.md (essential project overview)
       ├── API.md (endpoint documentation)
       └── OPERATIONS.md (deployment/config)
       ```
    3. Move current READMEs to new structure
    4. Archive everything else: `mkdir -p archives/old_docs && mv seeding_pipeline/docs/* archives/old_docs/`
    5. Remove archives: `rm -rf archives`
  - Validation: Verify new structure with `tree docs/`

### Task 4.2: Remove Completed Plans and Reports
- [x] Clean historical development artifacts
  - Purpose: Remove hundreds of completion/validation reports
  - Steps:
    1. Remove all completed plans: `find . -path "*/plans/completed" -type d -exec rm -rf {} +`
    2. Remove validation reports: `find . -name "*validation*.md" -o -name "*completion*.md" | xargs rm -f`
    3. Remove implementation reports: `find . -name "*implementation*.md" -o -name "*report*.md" | xargs rm -f`
  - Validation: Check remaining docs: `find docs/ -name "*.md" | wc -l` should be < 10

## Phase 5: Configuration Optimization

### Task 5.1: Consolidate Configuration Files
- [x] Merge and minimize configuration
  - Purpose: Reduce configuration sprawl
  - Steps:
    1. Use context7 MCP tool to review configuration management
    2. Identify all config files: `find . -name "*.yml" -o -name "*.yaml" -o -name "*.ini"`
    3. Create single `config/` directory at root
    4. Consolidate similar configs (keep production vs dev separation)
    5. Remove redundant configs
  - Validation: Count config files: `find . -name "*.yml" -o -name "*.yaml" | wc -l`

### Task 5.2: Create Docker Configuration
- [x] Replace venv with lightweight Docker setup
  - Purpose: Enable development without local storage overhead
  - Steps:
    1. Use context7 MCP tool to review Docker best practices
    2. Create minimal multi-stage Dockerfile for both projects
    3. Create docker-compose.yml for local development
    4. Update README with Docker instructions
  - Validation: Test build: `docker-compose build --no-cache`

## Phase 6: Final Cleanup and Verification

### Task 6.1: Remove Python Cache
- [ ] Clean all Python cache directories
  - Purpose: Remove __pycache__ directories
  - Steps:
    1. Run: `find . -type d -name "__pycache__" -exec rm -rf {} +`
    2. Run: `find . -name "*.pyc" -delete`
    3. Run: `find . -name "*.pyo" -delete`
  - Validation: Verify with `find . -name "__pycache__" | wc -l` shows 0

### Task 6.2: Git Repository Optimization
- [ ] Optimize git storage
  - Purpose: Reduce .git directory size
  - Steps:
    1. Use context7 MCP tool to review git maintenance
    2. Run: `git gc --aggressive --prune=now`
    3. Run: `git repack -a -d --depth=250 --window=250`
  - Validation: Check .git size: `du -sh .git`

### Task 6.3: Final Storage Verification
- [ ] Measure and document final results
  - Purpose: Confirm storage goals achieved
  - Steps:
    1. Measure total size: `du -sh /home/sergeblumenfeld/podcastknowledge`
    2. Measure by directory: `du -sh /home/sergeblumenfeld/podcastknowledge/*`
    3. Create storage report in OPERATIONS.md
    4. Verify all tests still pass
  - Validation: Total size should be < 50 MB

## Success Criteria

1. **Storage Reduction**: Project size reduced from 1.057 GB to < 50 MB
2. **Functionality Preserved**: All tests pass, code remains operational
3. **AI-Optimized Structure**: Minimal files, clear organization for Claude Code
4. **No Storage Creep**: .gitignore prevents future bloat
5. **Docker-Ready**: Can develop without local virtual environments

## Technology Requirements

### Existing Technologies (No approval needed)
- Git for version control
- Python (already in use)
- Basic Unix commands

### New Technologies (Requires approval)
- **Docker**: For replacing virtual environments
  - Benefit: Zero local storage for dependencies
  - Alternative: Continue using venv but exclude from repo

## Risk Mitigation

1. **Before starting**: Create full backup: `tar -czf podcast_backup_$(date +%Y%m%d).tar.gz /home/sergeblumenfeld/podcastknowledge`
2. **Test preservation**: Run test suite after each phase
3. **Incremental approach**: Complete each phase fully before proceeding
4. **Validation steps**: Each task includes verification

## Execution Notes

- This plan is designed for Claude Code execution
- Each task is atomic and can be executed independently
- Use context7 MCP tool for documentation lookup at each phase
- No human intuition required - all steps are explicit
- Total execution time: Approximately 30-60 minutes