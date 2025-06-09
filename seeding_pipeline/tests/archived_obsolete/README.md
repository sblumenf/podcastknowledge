# Archived Obsolete Tests

This directory contains tests that were archived because they reference APIs or functionality that no longer exists in the current codebase.

## Archived Tests

### test_checkpoint_recovery.py
- **Reason**: Uses obsolete checkpoint APIs (`save_progress`, `get_progress`, `process_podcast`)
- **Original Location**: tests/integration/
- **Tests Count**: 8
- **Issues**: Tests written for older checkpoint system that has been replaced

### test_cli_commands.py  
- **Reason**: References `cli.VTTKnowledgeExtractor` which doesn't exist in CLI module
- **Original Location**: tests/integration/
- **Tests Count**: 17
- **Issues**: CLI interface has changed significantly, tests need complete rewrite

## Why Archive Instead of Delete?

1. **Historical Reference**: These tests document how the system used to work
2. **Migration Guide**: Can help understand API evolution
3. **Potential Reuse**: Some test logic might be salvageable for new tests
4. **Git History**: Preserves context for future developers

## Restoration Guidelines

If you need to restore any of these tests:
1. Update API calls to match current implementation
2. Review current architecture in src/
3. Use existing working tests as templates
4. Consider if the test is still relevant to current functionality