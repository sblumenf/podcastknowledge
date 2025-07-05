# Shared Scripts

This directory contains scripts that are used across multiple modules or provide cross-module functionality.

## Scripts

### Tracking and Synchronization
- `test_simple_tracking.sh` - Test basic tracking functionality
- `test_tracking_sync.sh` - Test tracking synchronization between modules
- `test_overlap_fix.py` - Test overlap detection and fixes

## Usage

These scripts can be run from any module directory that needs cross-module functionality:
```bash
../../shared/scripts/test_tracking_sync.sh
```

## Adding New Shared Scripts

When adding new scripts to this directory, ensure they:
1. Are truly cross-module in nature
2. Don't have module-specific dependencies
3. Are documented with their purpose and usage
4. Follow the project's naming conventions