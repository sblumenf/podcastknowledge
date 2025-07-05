# Script Migration Guide

This guide documents the script reorganization that was performed to improve project structure and maintainability.

## Overview

Scripts have been reorganized from a flat structure into a hierarchical organization based on their purpose and the module they serve.

## Migration Summary

### Root Directory Changes

**Scripts that remain at root:**
- `run_pipeline.sh` - Cross-module orchestration
- `run_clustering.sh` - Clustering orchestration
- `add_podcast.sh` - Multi-podcast management
- `list_podcasts.sh` - Multi-podcast listing
- `update_youtube_url.sh` - Cross-podcast URL updates

**Scripts moved to seeding_pipeline:**
- `list_databases.py` → `seeding_pipeline/scripts/database/`
- `count_knowledge_units.py` → `seeding_pipeline/scripts/analysis/`
- `diagnose_meaningful_units.py` → `seeding_pipeline/scripts/analysis/`
- `explore_cluster_connections.py` → `seeding_pipeline/scripts/analysis/`
- `find_313_segment_episode.py` → `seeding_pipeline/scripts/analysis/`

**Scripts moved to shared:**
- `test_simple_tracking.sh` → `shared/scripts/`
- `test_tracking_sync.sh` → `shared/scripts/`
- `test_overlap_fix.py` → `shared/scripts/`

### Seeding Pipeline Reorganization

The flat `scripts/` directory has been organized into:

```
scripts/
├── setup/         # Installation and environment setup
├── database/      # Database operations and management
├── analysis/      # Data analysis and diagnostics
├── testing/       # Test runners and test utilities
├── monitoring/    # Performance and health monitoring
├── maintenance/   # Fixes, cleanup, and maintenance
├── validation/    # Deployment and quality validation
└── benchmarks/    # Performance benchmarking
```

### Transcriber Reorganization

```
scripts/
├── setup/         # Environment setup
├── maintenance/   # Audits and migrations
└── utilities/     # Transcription utilities
```

**Moved scripts:**
- `check_transcribed.py` → `scripts/utilities/`
- `find_next_episodes.py` → `scripts/utilities/`

## Finding Scripts

### Quick Reference

**Need to work with the database?**
Look in: `seeding_pipeline/scripts/database/`

**Need to analyze data?**
Look in: `seeding_pipeline/scripts/analysis/`

**Need to run tests?**
Look in: `seeding_pipeline/scripts/testing/`

**Need to check transcriptions?**
Look in: `transcriber/scripts/utilities/`

**Need cross-module functionality?**
Look in: `shared/scripts/`

### Using grep to find scripts

Find a script by name pattern:
```bash
find . -name "*episode*.py" -type f | grep -E "scripts/"
```

Find scripts by content:
```bash
grep -r "def main" --include="*.py" */scripts/
```

## Updating Your Workflows

If you have scripts or automation that references the old locations, update them:

### Example Updates

**Old:**
```bash
python list_databases.py
```

**New:**
```bash
python seeding_pipeline/scripts/database/list_databases.py
```

**Old:**
```bash
cd seeding_pipeline && python scripts/analyze_episode_segments.py
```

**New:**
```bash
cd seeding_pipeline && python scripts/analysis/analyze_episode_segments.py
```

## Benefits of New Organization

1. **Easier Discovery**: Scripts are grouped by purpose
2. **Clear Module Boundaries**: Each module owns its scripts
3. **Reduced Duplication**: Shared scripts are centralized
4. **Better Maintenance**: Related scripts are together
5. **Consistent Structure**: All modules follow same pattern

## Questions?

Refer to:
- `SCRIPT_INVENTORY.md` - Complete list of all scripts
- `*/scripts/README.md` - Module-specific script documentation
- Script docstrings - Individual script documentation